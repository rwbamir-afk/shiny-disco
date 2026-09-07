"""Private rooms service (Section 27)."""
from __future__ import annotations

import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Room, RoomPlayer


def _gen_invite() -> str:
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]


async def create_room(db: AsyncSession, creator_id: str, config: dict | None = None) -> Room:
    room = Room(
        creator_id=creator_id,
        status="waiting",
        config=json.dumps({"ready": [False, False, False, False]}),
        invite_code=_gen_invite(),
    )
    db.add(room)
    await db.flush()
    db.add(RoomPlayer(room_id=room.id, user_id=creator_id, seat=0))
    await db.commit()
    return room


async def get_room(db: AsyncSession, room_id: str) -> Room | None:
    return await db.get(Room, room_id)


async def get_room_by_invite(db: AsyncSession, invite_code: str) -> Room | None:
    res = await db.execute(select(Room).where(Room.invite_code == invite_code))
    return res.scalar_one_or_none()


async def join_room(db: AsyncSession, room: Room, user_id: str) -> int | None:
    """Add a player at the lowest free seat. Returns seat or None if full. Idempotent."""
    players = (
        (await db.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id)))
        .scalars()
        .all()
    )
    if any(p.user_id == user_id for p in players):
        # Already in the room.
        return next(p.seat for p in players if p.user_id == user_id)
    occupied = {p.seat for p in players}
    free = [s for s in range(4) if s not in occupied]
    if not free:
        return None
    seat = free[0]
    db.add(RoomPlayer(room_id=room.id, user_id=user_id, seat=seat))
    await db.commit()
    return seat


async def room_players_out(db: AsyncSession, room: Room) -> list[dict]:
    from ..models import User
    from .user_service import get_user

    players = (
        (await db.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id).order_by(RoomPlayer.seat)))
        .scalars()
        .all()
    )
    ready = json.loads(room.config or "{}").get("ready", [False, False, False, False])
    out = []
    for p in players:
        user = await db.get(User, p.user_id)
        out.append(
            {
                "user_id": p.user_id,
                "seat": p.seat,
                "username": user.username if user else None,
                "display_name": user.first_name if user else "",
                "is_bot": False,
                "ready": bool(ready[p.seat]) if p.seat < len(ready) else False,
            }
        )
    return out


async def mark_ready(db: AsyncSession, room: Room, user_id: str, ready: bool) -> None:
    players = (
        (await db.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id)))
        .scalars()
        .all()
    )
    seat = next((p.seat for p in players if p.user_id == user_id), None)
    if seat is None:
        raise ValueError("not in room")
    cfg = json.loads(room.config or "{}")
    r = list(cfg.get("ready", [False, False, False, False]))
    while len(r) < 4:
        r.append(False)
    r[seat] = ready
    cfg["ready"] = r
    room.config = json.dumps(cfg)
    await db.commit()


async def room_ready_states(db: AsyncSession, room: Room) -> list[bool]:
    return list(json.loads(room.config or "{}").get("ready", [False, False, False, False])[:4])
