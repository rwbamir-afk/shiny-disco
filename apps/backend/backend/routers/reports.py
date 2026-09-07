"""Reports router (Section 46)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import Report
from ..schemas import ReportIn, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/reasons")
async def reasons():
    return ["cheating", "abusive", "bad_behavior", "exploit", "other"]


@router.post("", response_model=ReportOut)
async def create_report(
    body: ReportIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if not body.reported_user_id and not body.game_id:
        raise ValueError("must specify a reported user or a game")
    r = Report(
        reporter_id=user.id,
        reported_user_id=body.reported_user_id,
        game_id=body.game_id,
        reason=body.reason,
        detail=body.detail,
    )
    db.add(r)
    await db.commit()
    return ReportOut(id=r.id, status=r.status, reason=r.reason)


@router.get("/mine", response_model=list[ReportOut])
async def my_reports(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(select(Report).where(Report.reporter_id == user.id).order_by(Report.created_at.desc())))
        .scalars()
        .all()
    )
    return [ReportOut(id=r.id, status=r.status, reason=r.reason) for r in rows]
