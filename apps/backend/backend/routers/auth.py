"""Auth router: Telegram init-data verification, refresh, logout (Section 24-26)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import RefreshSession, User
from ..schemas import AuthResponse, ProfileOut, RefreshIn, TelegramAuthIn, TokenPair, UserOut
from ..security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_telegram_init_data,
)
from ..services.user_service import profile_public, upsert_user_from_telegram

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(body: TelegramAuthIn, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    try:
        tg = verify_telegram_init_data(body.init_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"invalid init_data: {e}")

    user = await upsert_user_from_telegram(db, tg)
    await db.commit()

    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(
        RefreshSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            expires_at=refresh_token_expiry(),
        )
    )
    await db.commit()

    profile = await _profile(db, user.id)
    return AuthResponse(
        user=UserOut(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            avatar_url=user.avatar_url,
        ),
        profile=ProfileOut(**profile),
        tokens=TokenPair(access_token=create_access_token(user.id), refresh_token=raw_refresh),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
    from datetime import datetime, timezone

    from ..models import RefreshSession

    hashed = hash_refresh_token(body.refresh_token)
    res = await db.execute(select(RefreshSession).where(RefreshSession.refresh_token_hash == hashed))
    sid = res.scalar_one_or_none()
    if sid is None or sid.revoked:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    expires = sid.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="refresh token expired")
    # Rotate: revoke the old session, issue a new refresh token.
    sid.revoked = True
    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(
        RefreshSession(
            user_id=sid.user_id,
            refresh_token_hash=refresh_hash,
            expires_at=refresh_token_expiry(),
        )
    )
    await db.commit()
    return TokenPair(access_token=create_access_token(sid.user_id), refresh_token=raw_refresh)


@router.post("/logout")
async def logout(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> dict:
    hashed = hash_refresh_token(body.refresh_token)
    res = await db.execute(select(RefreshSession).where(RefreshSession.refresh_token_hash == hashed))
    sid = res.scalar_one_or_none()
    if sid is not None:
        sid.revoked = True
        await db.commit()
    return {"ok": True, "message": "logged out"}


async def _profile(db: AsyncSession, user_id: str) -> dict:
    from ..services.user_service import get_profile

    profile = await get_profile(db, user_id)
    user = await db.get(User, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile")
    return profile_public(profile, user)
