"""Users + profiles router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import ProfileOut, UserOut, ProfileUpdateIn, SettingsUpdateIn
from ..services.user_service import get_profile, profile_public
from datetime import datetime, timezone

router = APIRouter(prefix="/users", tags=["users"])


async def _to_out(user: User, db: AsyncSession, touch: bool = False) -> dict:
    profile = await get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile")
    if touch:
        profile.last_seen = datetime.now(timezone.utc)
    return {
        "user": UserOut(
            id=user.id, telegram_id=user.telegram_id, username=user.username,
            first_name=user.first_name, last_name=user.last_name, avatar_url=user.avatar_url,
        ),
        "profile": ProfileOut(**profile_public(profile, user)),
    }


@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _to_out(user, db, touch=True)


@router.get("/{user_id}")
async def get_public_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None or user.is_blocked:
        raise HTTPException(status_code=404, detail="user not found")
    profile = await get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile")
    if not profile.public_profile:
        return {"user": {"id": user.id, "display_name": user.first_name or "بازیکن"}, "profile": {"user_id": user.id, "public": False}}
    return await _to_out(user, db)


@router.patch("/me/profile")
async def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    profile.bio = body.bio.strip()
    profile.profile_title = body.profile_title.strip()
    await db.commit()
    return {"ok": True, "bio": profile.bio, "profile_title": profile.profile_title}


@router.get("/me/settings")
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    fields = ["show_online", "allow_friend_requests", "public_profile", "notify_friend_requests",
              "notify_friend_accepts", "notify_rewards", "sound_enabled", "vibration_enabled",
              "compact_cards", "auto_sort_hand", "preferred_card_speed", "theme", "language"]
    return {key: getattr(profile, key) for key in fields}


@router.patch("/me/settings")
async def update_settings(body: SettingsUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await get_profile(db, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    values = body.model_dump(exclude_none=True)
    for key, value in values.items():
        setattr(profile, key, value)
    await db.commit()
    return {"ok": True, **{key: getattr(profile, key) for key in (
        "show_online", "allow_friend_requests", "public_profile", "notify_friend_requests",
        "notify_friend_accepts", "notify_rewards", "sound_enabled", "vibration_enabled",
        "compact_cards", "auto_sort_hand", "preferred_card_speed", "theme", "language")}}
