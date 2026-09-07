"""Progression, missions and achievements API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..services.progression_service import sync_progress, claim_mission

router = APIRouter(prefix="/progression", tags=["progression"])

@router.get("")
async def get_progress(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await sync_progress(db, user.id)
    await db.commit()
    return result

@router.post("/missions/{mission_id}/claim")
async def claim(mission_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await claim_mission(db, user.id, mission_id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
