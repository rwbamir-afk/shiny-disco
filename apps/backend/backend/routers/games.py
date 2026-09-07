"""Games router: view/snapshot retrieval, REST action endpoint (also used over WebSocket)."""
from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import User, Game as GameModel, GamePlayer, UserProfile, Move, GameSpectator
from ..schemas import GameActionIn, ResultOut

router = APIRouter(prefix="/games", tags=["games"])


@router.post("/{game_id}/spectate")
async def spectate(game_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    gs = request.app.state.game_service
    runtime = gs.registry.get(game_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="live game not found")
    if runtime.seat_for_user(user.id) is not None:
        return {"ok": True, "status": "participant", "view": gs.view_payload(runtime, runtime.seat_for_user(user.id))}
    existing = (await db.execute(select(GameSpectator).where(GameSpectator.game_id == game_id, GameSpectator.user_id == user.id))).scalar_one_or_none()
    if existing is None:
        db.add(GameSpectator(game_id=game_id, user_id=user.id))
        await db.commit()
    request.app.state.conn.subscribe_spectator(game_id, user.id)
    return {"ok": True, "status": "spectating", "view": gs.spectator_payload(runtime)}

@router.delete("/{game_id}/spectate")
async def leave_spectate(game_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(GameSpectator).where(GameSpectator.game_id == game_id, GameSpectator.user_id == user.id))).scalar_one_or_none()
    if row:
        await db.delete(row); await db.commit()
    request.app.state.conn.unsubscribe_spectator(game_id, user.id)
    return {"ok": True}

@router.get("/{game_id}/spectators")
async def spectators(game_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(GameSpectator).where(GameSpectator.game_id == game_id))).scalars().all()
    return {"game_id": game_id, "count": len(rows), "spectator_ids": [r.user_id for r in rows]}

@router.get("/{game_id}/view")
async def get_view(game_id: str, request: Request, user: User = Depends(get_current_user)):
    gs = request.app.state.game_service
    runtime = gs.registry.get(game_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="game not found")
    seat = runtime.seat_for_user(user.id)
    if seat is None:
        raise HTTPException(status_code=403, detail="not a participant")
    return {"ok": True, "view": gs.view_payload(runtime, seat)}



@router.get("/{game_id}/replay")
async def replay(game_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    game = await db.get(GameModel, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    player = (await db.execute(select(GamePlayer).where(GamePlayer.game_id == game_id, GamePlayer.user_id == user.id))).scalar_one_or_none()
    if player is None:
        raise HTTPException(status_code=403, detail="not a participant")
    moves = (await db.execute(select(Move).where(Move.game_id == game_id).order_by(Move.move_number))).scalars().all()
    return {"game_id": game_id, "winner_team": game.winner_team, "scores": json.loads(game.final_scores or "{}"),
            "moves": [{"move_number": m.move_number, "seat": m.seat, "action": m.action, "card": m.card, "trump": m.trump, "server_time": m.server_time.isoformat() if m.server_time else None} for m in moves]}

@router.get("/{game_id}/fairness")
async def fairness(game_id: str, db: AsyncSession = Depends(get_db)):
    game = await db.get(GameModel, game_id)
    if game is None: raise HTTPException(404, "game not found")
    revealed = game.status == "finished" and game.fairness_nonce is not None
    return {"game_id": game.id, "commitment": game.fairness_commitment, "revealed": revealed,
            "seed": game.seed if revealed else None, "nonce": game.fairness_nonce if revealed else None}

@router.get("/{game_id}/result", response_model=ResultOut)
async def get_result(game_id: str, request: Request, user: User = Depends(get_current_user)):
    gs = request.app.state.game_service
    runtime = gs.registry.get(game_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="game not found")
    if not runtime.finished:
        raise HTTPException(status_code=409, detail="game not finished")
    res = runtime.engine.result()
    async with request.app.state.session_factory() as db:
        rows = (await db.execute(select(GamePlayer).where(GamePlayer.game_id == game_id))).scalars().all()
    rating_changes = {r.user_id: r.rating_change for r in rows if r.user_id}
    xp_changes = {r.user_id: r.xp_gained for r in rows if r.user_id}
    coin_changes = {r.user_id: r.coins_gained for r in rows if r.user_id}
    return ResultOut(
        game_id=game_id, winner_team=res["winner_team"], scores=res["scores"],
        rating_changes=rating_changes, xp_changes=xp_changes, coin_changes=coin_changes,
    )



@router.get("/history/mine")
async def my_history(limit: int = 30, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 100))
    rows = (await db.execute(
        select(GameModel, GamePlayer)
        .join(GamePlayer, GamePlayer.game_id == GameModel.id)
        .where(GamePlayer.user_id == user.id, GameModel.status == "finished")
        .order_by(GameModel.finished_at.desc())
        .limit(limit)
    )).all()
    out = []
    for game, player in rows:
        scores = json.loads(game.final_scores or "{}")
        won = game.winner_team == player.team
        out.append({"game_id": game.id, "finished_at": game.finished_at.isoformat() if game.finished_at else None,
                    "team": player.team, "won": won, "scores": scores,
                    "rating_change": player.rating_change, "xp_gained": player.xp_gained, "coins_gained": player.coins_gained})
    return {"games": out}

@router.post("/{game_id}/action")
async def post_action(
    game_id: str, body: GameActionIn, request: Request, user: User = Depends(get_current_user)
):
    gs = request.app.state.game_service
    out = await gs.handle_action(game_id, user.id, body.model_dump())
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("error", "bad action"))
    return {"ok": True, "view": out.get("view")}
