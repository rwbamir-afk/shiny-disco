"""Private rooms router (Section 27)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..config import get_settings
from ..models import User, UserProfile, Room, RoomPlayer
from ..schemas import CreateRoomIn, JoinRoomIn, MessageOut, RoomOut, RoomReadyIn
from ..services import room_service

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _to_out(room, players) -> RoomOut:
    return RoomOut(
        id=room.id, creator_id=room.creator_id, status=room.status,
        invite_code=room.invite_code, rules_version=room.rules_version, players=players,
    )


@router.post("", response_model=RoomOut)
async def create_room(body: CreateRoomIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await room_service.create_room(db, user.id, body.config)
    return _to_out(room, await room_service.room_players_out(db, room))


@router.post("/join", response_model=RoomOut)
async def join_room(body: JoinRoomIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await room_service.get_room_by_invite(db, body.invite_code)
    if room is None or room.status in ("starting", "ingame", "closed"):
        raise HTTPException(status_code=404, detail="room not available")
    seat = await room_service.join_room(db, room, user.id)
    if seat is None:
        raise HTTPException(status_code=409, detail="room is full")
    return _to_out(room, await room_service.room_players_out(db, room))


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await room_service.get_room(db, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    return _to_out(room, await room_service.room_players_out(db, room))


@router.post("/{room_id}/ready", response_model=MessageOut)
async def ready(room_id: str, body: RoomReadyIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await room_service.get_room(db, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    await room_service.mark_ready(db, room, user.id, body.ready)
    return MessageOut(message="ok")


@router.post("/{room_id}/start", response_model=RoomOut)
async def start_game(room_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await room_service.get_room(db, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room not found")
    if room.creator_id != user.id:
        raise HTTPException(status_code=403, detail="only the creator can start")
    players = await room_service.room_players_out(db, room)
    if len(players) < 2:
        raise HTTPException(status_code=409, detail="need at least 2 players")
    ready_states = await room_service.room_ready_states(db, room)
    if not all(bool(ready_states[p["seat"]]) for p in players):
        raise HTTPException(status_code=409, detail="not all players are ready")

    seats = []
    for p in players:
        prof = (
            (await db.execute(select(UserProfile).where(UserProfile.user_id == p["user_id"])))
            .scalar_one_or_none()
        )
        seats.append(
            {"user_id": p["user_id"], "is_bot": False, "rating": prof.rating if prof else 1000,
             "display_name": p["display_name"], "username": p["username"]}
        )
    while len(seats) < 4:
        seats.append(
            {"user_id": f"bot_{len(seats)}", "is_bot": True, "bot_difficulty": "medium",
             "display_name": f"ربات {len(seats)}", "username": None, "rating": 1000}
        )

    game_service = request.app.state.game_service
    await game_service.create_game(seats, db=db, config={"source": "room", "room_id": room_id})
    room.status = "ingame"
    await db.commit()
    return _to_out(room, await room_service.room_players_out(db, room))


@router.get("/{room_id}/invite")
async def room_invite(room_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "room not found")
    member = (await db.execute(select(RoomPlayer.id).where(RoomPlayer.room_id == room_id, RoomPlayer.user_id == user.id))).scalar_one_or_none()
    if not member:
        raise HTTPException(403, "not a room member")
    settings = get_settings()
    if not settings.telegram_bot_username:
        raise HTTPException(503, "telegram bot username is not configured")
    target = f"https://t.me/{settings.telegram_bot_username}"
    if settings.telegram_mini_app_short_name:
        target += f"?startapp=room_{room.invite_code}"
    else:
        target += f"?start=room_{room.invite_code}"
    return {"invite_code": room.invite_code, "url": target, "text": f"بیا توی بازی حکم من 🎴\n{target}"}
