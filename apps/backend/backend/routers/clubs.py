"""Club/guild APIs with owner/officer permissions and membership limits."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import Club, ClubJoinRequest, ClubMember, User

router = APIRouter(prefix="/clubs", tags=["clubs"])

class ClubCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    tag: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9_]+$")
    description: str = Field(default="", max_length=240)
    privacy: str = Field(default="open", pattern=r"^(open|invite|closed)$")
    max_members: int = Field(default=100, ge=5, le=500)

class ClubUpdateIn(BaseModel):
    description: str | None = Field(default=None, max_length=240)
    privacy: str | None = Field(default=None, pattern=r"^(open|invite|closed)$")
    max_members: int | None = Field(default=None, ge=5, le=500)

async def member_row(db, club_id: str, user_id: str):
    return (await db.execute(select(ClubMember).where(ClubMember.club_id == club_id, ClubMember.user_id == user_id))).scalar_one_or_none()

def serialize(c: Club, members: int):
    return {"id": c.id, "owner_id": c.owner_id, "name": c.name, "tag": c.tag, "description": c.description, "privacy": c.privacy, "max_members": c.max_members, "members": members, "level": c.level, "xp": c.xp}

@router.post("")
async def create_club(body: ClubCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(Club.id).where(Club.tag == body.tag.upper()))).scalar_one_or_none():
        raise HTTPException(409, "club tag already exists")
    club = Club(owner_id=user.id, name=body.name.strip(), tag=body.tag.upper(), description=body.description.strip(), privacy=body.privacy, max_members=body.max_members)
    db.add(club); await db.flush(); db.add(ClubMember(club_id=club.id, user_id=user.id, role="owner")); await db.commit()
    return serialize(club, 1)

@router.get("")
async def list_clubs(q: str = "", limit: int = 20, offset: int = 0, db: AsyncSession = Depends(get_db)):
    stmt = select(Club).order_by(Club.level.desc(), Club.xp.desc()).offset(max(0, offset)).limit(min(limit, 50))
    if q.strip():
        term = q.strip()[:40]; stmt = stmt.where((Club.name.ilike(f"%{term}%")) | (Club.tag.ilike(f"%{term.upper()}%")))
    clubs = (await db.execute(stmt)).scalars().all()
    counts = {x[0]: x[1] for x in (await db.execute(select(ClubMember.club_id, func.count(ClubMember.id)).where(ClubMember.club_id.in_([c.id for c in clubs])).group_by(ClubMember.club_id))).all()} if clubs else {}
    return {"clubs": [serialize(c, int(counts.get(c.id, 0))) for c in clubs]}

@router.get("/{club_id}")
async def get_club(club_id: str, db: AsyncSession = Depends(get_db)):
    club = await db.get(Club, club_id)
    if not club: raise HTTPException(404, "club not found")
    rows = (await db.execute(select(ClubMember, User).join(User, User.id == ClubMember.user_id).where(ClubMember.club_id == club_id).order_by(ClubMember.role, ClubMember.created_at))).all()
    return {"club": serialize(club, len(rows)), "members": [{"user_id": m.user_id, "display_name": u.first_name or u.username or "بازیکن", "username": u.username, "role": m.role, "contribution_xp": m.contribution_xp} for m, u in rows]}

@router.post("/{club_id}/join")
async def join_club(club_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    club = await db.get(Club, club_id)
    if not club: raise HTTPException(404, "club not found")
    if await member_row(db, club_id, user.id): return {"ok": True, "status": "member"}
    count = await db.scalar(select(func.count(ClubMember.id)).where(ClubMember.club_id == club_id))
    if count >= club.max_members: raise HTTPException(409, "club is full")
    if club.privacy == "closed": raise HTTPException(403, "club is closed")
    if club.privacy == "invite": raise HTTPException(403, "invite required")
    db.add(ClubMember(club_id=club_id, user_id=user.id)); await db.commit(); return {"ok": True, "status": "member"}

@router.post("/{club_id}/requests")
async def request_join(club_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    club = await db.get(Club, club_id)
    if not club: raise HTTPException(404, "club not found")
    if club.privacy != "invite": raise HTTPException(400, "join requests are only needed for invite clubs")
    if await member_row(db, club_id, user.id): return {"ok": True, "status": "member"}
    req = (await db.execute(select(ClubJoinRequest).where(ClubJoinRequest.club_id == club_id, ClubJoinRequest.user_id == user.id))).scalar_one_or_none()
    if req: req.status = "pending"
    else: db.add(ClubJoinRequest(club_id=club_id, user_id=user.id, status="pending"))
    await db.commit(); return {"ok": True, "status": "pending"}

@router.post("/{club_id}/requests/{request_id}/accept")
async def accept_request(club_id: str, request_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    actor = await member_row(db, club_id, user.id)
    if not actor or actor.role not in {"owner", "officer"}: raise HTTPException(403, "insufficient club permissions")
    req = await db.get(ClubJoinRequest, request_id)
    club = await db.get(Club, club_id)
    if not req or req.club_id != club_id or req.status != "pending": raise HTTPException(404, "request not found")
    count = await db.scalar(select(func.count(ClubMember.id)).where(ClubMember.club_id == club_id))
    if count >= club.max_members: raise HTTPException(409, "club is full")
    req.status = "accepted"; db.add(ClubMember(club_id=club_id, user_id=req.user_id)); await db.commit(); return {"ok": True}

@router.delete("/{club_id}/members/{member_id}")
async def remove_member(club_id: str, member_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    actor = await member_row(db, club_id, user.id)
    target = await member_row(db, club_id, member_id)
    if not actor or actor.role not in {"owner", "officer"}: raise HTTPException(403, "insufficient club permissions")
    if not target: raise HTTPException(404, "member not found")
    if target.role == "owner": raise HTTPException(400, "owner cannot be removed")
    db.delete(target); await db.commit(); return {"ok": True}
