"""Matchmaking router (Section 16/28/29)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import MatchmakingIn, MatchmakingStatusOut

router = APIRouter(prefix="/matchmaking", tags=["matchmaking"])


@router.post("/quick", response_model=MatchmakingStatusOut)
async def quick_match(
    body: MatchmakingIn, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    mm = request.app.state.matchmaking
    await mm.enqueue(user.id)
    return MatchmakingStatusOut(status="searching")


@router.get("/status", response_model=MatchmakingStatusOut)
async def status(request: Request, user: User = Depends(get_current_user)):
    mm = request.app.state.matchmaking
    st = await mm.status(user.id)
    return MatchmakingStatusOut(status=st.get("status", "no_game"), game_id=st.get("game_id"))


@router.post("/cancel", response_model=MatchmakingStatusOut)
async def cancel(request: Request, user: User = Depends(get_current_user)):
    mm = request.app.state.matchmaking
    await mm.dequeue(user.id)
    return MatchmakingStatusOut(status="no_game")
