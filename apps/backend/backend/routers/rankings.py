"""Rankings router (Section 38). Server-calculated only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User, UserProfile
from ..schemas import RankingEntry
from ..services.user_service import rank_tier
from ..deps import get_current_user

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("/global", response_model=list[RankingEntry])
async def global_ranking(limit: int = Query(50, le=500), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(UserProfile, User)
            .join(User, UserProfile.user_id == User.id)
            .where(User.is_bot == False)  # noqa: E712
            .order_by(UserProfile.rating.desc())
            .limit(limit)
        )
    ).all()
    return [
        RankingEntry(
            user_id=prof.user_id,
            display_name=(user.first_name or user.username or "کاربر"),
            rating=prof.rating,
            games_played=prof.games_played,
            wins=prof.wins,
            rank_tier=rank_tier(prof.rating),
        )
        for prof, user in rows
    ]


@router.get("/weekly", response_model=list[RankingEntry])
async def weekly_ranking(limit: int = Query(50, le=500), db: AsyncSession = Depends(get_db)):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # MVP approximation: players active in the last 7 days, ordered by rating.
    rows = (
        await db.execute(
            select(UserProfile, User)
            .join(User, UserProfile.user_id == User.id)
            .where(User.is_bot == False, UserProfile.last_seen >= week_ago)  # noqa: E712
            .order_by(UserProfile.rating.desc())
            .limit(limit)
        )
    ).all()
    return [
        RankingEntry(
            user_id=prof.user_id,
            display_name=(user.first_name or user.username or "کاربر"),
            rating=prof.rating,
            games_played=prof.games_played,
            wins=prof.wins,
            rank_tier=rank_tier(prof.rating),
        )
        for prof, user in rows
    ]


@router.get("/me/position")
async def my_position(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404, "profile not found")
    ahead = (await db.execute(select(UserProfile.user_id).where(UserProfile.rating > profile.rating))).scalars().all()
    return {"position": len(ahead) + 1, "rating": profile.rating, "tier": rank_tier(profile.rating)}

@router.get("/around-me")
async def around_me(window: int = Query(3, ge=1, le=10), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404, "profile not found")
    ahead = (await db.execute(select(func.count(UserProfile.user_id)).where(UserProfile.rating > profile.rating))).scalar_one()
    position = int(ahead) + 1
    rows = (await db.execute(select(UserProfile, User).join(User, UserProfile.user_id == User.id).where(User.is_bot == False).order_by(UserProfile.rating.desc()).offset(max(0, position - window - 1)).limit(window * 2 + 1))).all()
    start = max(1, position - window)
    return {"position": position, "entries": [{"position": start + i, "user_id": p.user_id, "display_name": u.first_name or u.username or "کاربر", "rating": p.rating, "rank_tier": rank_tier(p.rating)} for i, (p, u) in enumerate(rows)]}


@router.get("/top")
async def top_players(limit: int = Query(10, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(UserProfile, User).join(User, UserProfile.user_id == User.id).where(User.is_bot == False).order_by(UserProfile.rating.desc(), UserProfile.wins.desc()).limit(limit))).all()
    return {"entries": [{"position": i + 1, "user_id": p.user_id, "display_name": u.first_name or u.username or "کاربر", "rating": p.rating, "wins": p.wins, "rank_tier": rank_tier(p.rating)} for i, (p, u) in enumerate(rows)]}

@router.get("/tier/{tier_key}")
async def tier_ranking(tier_key: str, limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    tiers = {"نوآموز": (0, 899), "سرباز": (900, 999), "سردار": (1000, 1099), "وزیر": (1100, 1199), "شاه": (1200, 999999)}
    bounds = tiers.get(tier_key)
    if not bounds:
        raise HTTPException(404, "tier not found")
    lo, hi = bounds
    rows = (await db.execute(select(UserProfile, User).join(User, UserProfile.user_id == User.id).where(User.is_bot == False, UserProfile.rating >= lo, UserProfile.rating <= hi).order_by(UserProfile.rating.desc()).limit(limit))).all()
    return {"tier": rank_tier(lo if tier_key != "شاه" else 1200), "entries": [{"user_id": p.user_id, "display_name": u.first_name or u.username or "کاربر", "rating": p.rating, "wins": p.wins} for p, u in rows]}

@router.get("/page")
async def ranking_page(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(UserProfile, User).join(User, UserProfile.user_id == User.id)
        .where(User.is_bot == False).order_by(UserProfile.rating.desc(), UserProfile.wins.desc())
        .offset(offset).limit(limit + 1)
    )).all()
    return {"offset": offset, "limit": limit, "has_more": len(rows) > limit,
            "entries": [{"position": offset + i + 1, "user_id": p.user_id, "display_name": u.first_name or u.username or "کاربر", "rating": p.rating, "wins": p.wins, "rank_tier": rank_tier(p.rating)} for i, (p, u) in enumerate(rows[:limit])]}

@router.get("/search")
async def ranking_search(q: str = Query(..., min_length=2, max_length=64), limit: int = Query(20, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    term = f"%{q.strip()}%"
    rows = (await db.execute(
        select(UserProfile, User).join(User, UserProfile.user_id == User.id)
        .where(User.is_bot == False, (User.username.ilike(term) | User.first_name.ilike(term)))
        .order_by(UserProfile.rating.desc()).limit(limit)
    )).all()
    return {"entries": [{"user_id": p.user_id, "display_name": u.first_name or u.username or "کاربر", "rating": p.rating, "wins": p.wins, "rank_tier": rank_tier(p.rating)} for p, u in rows]}
