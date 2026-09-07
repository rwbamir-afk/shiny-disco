"""Basic admin router (Section 47). Server-side admin roles enforced."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import require_admin
from ..models import AuditLog, Game, Report, User
from ..schemas import MessageOut
from ..services.user_service import get_profile, profile_public

router = APIRouter(prefix="/admin", tags=["admin"])


async def _audit(db: AsyncSession, actor_id: str, action: str, target_type: str | None, target_id: str | None, detail: dict | None = None):
    db.add(
        AuditLog(
            actor_id=actor_id, action=action, target_type=target_type,
            target_id=target_id, detail=json.dumps(detail or {}),
        )
    )
    await db.commit()


@router.get("/users/search")
async def search_users(
    q: str = Query(...), admin=Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    rows = (
        await db.execute(
            select(User).where((User.username.ilike(f"%{q}%")) | (User.telegram_id == (int(q) if q.isdigit() else -1)))
        )
    ).scalars().all()
    return [{"id": u.id, "username": u.username, "first_name": u.first_name, "telegram_id": u.telegram_id, "is_blocked": u.is_blocked} for u in rows]


@router.get("/games/{game_id}")
async def inspect_game(game_id: str, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from ..models import GameEvent, GamePlayer, Move

    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    players = (
        (await db.execute(select(GamePlayer).where(GamePlayer.game_id == game_id))).scalars().all()
    )
    moves = (
        (await db.execute(select(Move).where(Move.game_id == game_id).order_by(Move.move_number))).scalars().all()
    )
    events = (
        (await db.execute(select(GameEvent).where(GameEvent.game_id == game_id).order_by(GameEvent.created_at))).scalars().all()
    )
    return {
        "game": {"id": game.id, "status": game.status, "winner_team": game.winner_team, "final_scores": game.final_scores,
                 "rules_version": game.rules_version, "seed": game.seed},
        "players": [{"seat": p.seat, "user_id": p.user_id, "team": p.team, "is_bot": p.is_bot, "conn": p.connection_state} for p in players],
        "moves": [{"n": m.move_number, "seat": m.seat, "action": m.action, "card": m.card, "trump": m.trump} for m in moves],
        "events": [{"event": e.event, "payload": e.payload} for e in events],
    }



@router.get("/games/{game_id}/audit")
async def audit_game(game_id: str, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Return deterministic anti-cheat signals; this never auto-bans a player."""
    from ..models import GameEvent, GamePlayer, Move
    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    moves = (await db.execute(select(Move).where(Move.game_id == game_id).order_by(Move.move_number))).scalars().all()
    events = (await db.execute(select(GameEvent).where(GameEvent.game_id == game_id).order_by(GameEvent.created_at))).scalars().all()
    players = (await db.execute(select(GamePlayer).where(GamePlayer.game_id == game_id))).scalars().all()
    illegal = [e for e in events if e.event in {"illegal_action", "malformed_action"}]
    takeovers = [e for e in events if e.event == "bot_takeover"]
    disconnects = [e for e in events if e.event == "player_disconnected"]
    rapid_pairs = 0
    for a, b in zip(moves, moves[1:]):
        if a.server_time and b.server_time and (b.server_time - a.server_time).total_seconds() < 0.20:
            rapid_pairs += 1
    score = min(100, len(illegal) * 20 + len(takeovers) * 8 + len(disconnects) * 3 + min(rapid_pairs, 10) * 2)
    flags = []
    if illegal: flags.append("illegal_actions")
    if rapid_pairs >= 3: flags.append("rapid_actions")
    if takeovers: flags.append("bot_takeover")
    if len(disconnects) >= 2: flags.append("repeated_disconnects")
    return {"game_id": game_id, "risk_score": score, "flags": flags,
            "counts": {"moves": len(moves), "illegal_actions": len(illegal), "rapid_pairs": rapid_pairs,
                       "bot_takeovers": len(takeovers), "disconnects": len(disconnects)},
            "players": [{"user_id": p.user_id, "seat": p.seat, "connection_state": p.connection_state} for p in players],
            "note": "Signals are review aids, not an automatic cheating verdict."}

@router.get("/reports")
async def list_reports(status: str = "open", admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(select(Report).where(Report.status == status).order_by(Report.created_at.desc())))
        .scalars().all()
    )
    return [{"id": r.id, "reporter": r.reporter_id, "reported": r.reported_user_id, "game_id": r.game_id,
             "reason": r.reason, "status": r.status} for r in rows]


@router.post("/reports/{report_id}/resolve", response_model=MessageOut)
async def resolve_report(report_id: str, action: str = "resolved", admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    r = await db.get(Report, report_id)
    if r is None:
        raise HTTPException(status_code=404, detail="report not found")
    r.status = action
    await _audit(db, admin.id, "resolve_report", "report", report_id)
    await db.commit()
    return MessageOut(message="resolved")


@router.post("/users/{user_id}/block", response_model=MessageOut)
async def block_user(user_id: str, admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    u.is_blocked = not u.is_blocked
    await _audit(db, admin.id, "toggle_block", "user", user_id, {"blocked": u.is_blocked})
    await db.commit()
    return MessageOut(message="blocked" if u.is_blocked else "unblocked")


@router.get("/health")
async def health():
    return {"ok": True, "app": "hokm"}

@router.get("/stats")
async def stats(admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from ..models import UserProfile
    users = int((await db.execute(select(func.count(User.id)))).scalar_one())
    active = int((await db.execute(select(func.count(User.id)).where(User.is_blocked == False))).scalar_one())
    games = int((await db.execute(select(func.count(Game.id)))).scalar_one())
    finished = int((await db.execute(select(func.count(Game.id)).where(Game.status == "finished"))).scalar_one())
    reports = int((await db.execute(select(func.count(Report.id)).where(Report.status == "open"))).scalar_one())
    return {"users": users, "active_users": active, "games": games, "finished_games": finished, "open_reports": reports}
