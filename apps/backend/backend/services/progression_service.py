"""Missions and achievement progression backed by durable user state."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Mission, UserMission, Achievement, UserAchievement, UserProfile
from .economy_service import credit
from .user_service import level_for_xp

MISSION_SEEDS = [
    ("first_game", "اولین بازی", "یک بازی کامل انجام بده", "games_played", 1, 50, 25),
    ("three_wins", "سه برد", "سه بازی را ببر", "wins", 3, 120, 60),
    ("five_games", "دست‌گرم", "پنج بازی انجام بده", "games_played", 5, 100, 50),
    ("win_streak_3", "سه‌تایی", "به برد متوالی ۳ برس", "streak", 3, 150, 80),
    ("level_5", "در مسیر استادی", "به سطح ۵ برس", "level", 5, 250, 100),
]
ACHIEVEMENT_SEEDS = [
    ("rookie", "بازیکن تازه‌وارد", "اولین بازی را کامل کن", "games_played", 1, 25, 20),
    ("veteran", "کهنه‌کار", "۲۵ بازی انجام بده", "games_played", 25, 250, 150),
    ("winner", "دست‌بالا", "۱۰ برد کسب کن", "wins", 10, 300, 200),
    ("hot_hand", "دست داغ", "به استریک ۵ برس", "max_streak", 5, 350, 250),
    ("rated", "رقابت‌جو", "به ریتینگ ۱۲۰۰ برس", "rating", 1200, 500, 300),
]

async def ensure_catalog(db: AsyncSession) -> None:
    for slug, title, desc, metric, target, coins, xp in MISSION_SEEDS:
        row = (await db.execute(select(Mission).where(Mission.slug == slug))).scalar_one_or_none()
        if not row:
            db.add(Mission(slug=slug, title=title, description=desc, metric=metric, target=target, reward_coins=coins, reward_xp=xp))
    for slug, title, desc, metric, target, coins, xp in ACHIEVEMENT_SEEDS:
        row = (await db.execute(select(Achievement).where(Achievement.slug == slug))).scalar_one_or_none()
        if not row:
            db.add(Achievement(slug=slug, title=title, description=desc, metric=metric, target=target, reward_coins=coins, reward_xp=xp))
    await db.flush()

async def _metric(profile: UserProfile, metric: str) -> int:
    return int(getattr(profile, metric, 0))

async def sync_progress(db: AsyncSession, user_id: str) -> dict:
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one()
    await ensure_catalog(db)
    missions = (await db.execute(select(Mission).where(Mission.active.is_(True)))).scalars().all()
    achievements = (await db.execute(select(Achievement).where(Achievement.active.is_(True)))).scalars().all()
    for mission in missions:
        um = (await db.execute(select(UserMission).where(UserMission.user_id == user_id, UserMission.mission_id == mission.id))).scalar_one_or_none()
        if not um:
            um = UserMission(user_id=user_id, mission_id=mission.id)
            db.add(um)
        um.progress = min(mission.target, await _metric(profile, mission.metric))
    await db.flush()
    return await snapshot_progress(db, user_id)

async def snapshot_progress(db: AsyncSession, user_id: str) -> dict:
    await ensure_catalog(db)
    missions = (await db.execute(select(UserMission, Mission).join(Mission, UserMission.mission_id == Mission.id).where(UserMission.user_id == user_id).order_by(Mission.id))).all()
    achievements = (await db.execute(select(UserAchievement, Achievement).join(Achievement, UserAchievement.achievement_id == Achievement.id).where(UserAchievement.user_id == user_id).order_by(Achievement.id))).all()
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one()
    unlocked = {ua.achievement_id for ua, _ in achievements if ua is not None}
    for _, a in achievements:
        if int(getattr(profile, a.metric, 0)) >= a.target:
            unlocked.add(a.id)
    return {
        "level": profile.level,
        "xp": profile.xp,
        "missions": [{"id": m.id, "slug": m.slug, "title": m.title, "description": m.description, "progress": um.progress, "target": m.target, "reward_coins": m.reward_coins, "reward_xp": m.reward_xp, "claimable": um.progress >= m.target and not um.claimed, "claimed": um.claimed} for um, m in missions],
        "achievements": [{"id": a.id, "slug": a.slug, "title": a.title, "description": a.description, "target": a.target, "reward_coins": a.reward_coins, "reward_xp": a.reward_xp, "unlocked": a.id in unlocked} for ua, a in achievements],
    }

async def claim_mission(db: AsyncSession, user_id: str, mission_id: str) -> dict:
    row = (await db.execute(select(UserMission, Mission).join(Mission, UserMission.mission_id == Mission.id).where(UserMission.user_id == user_id, UserMission.mission_id == mission_id))).first()
    if not row:
        raise ValueError("mission not found")
    um, mission = row
    if um.claimed or um.progress < mission.target:
        raise ValueError("mission is not claimable")
    um.claimed = True
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one()
    profile.xp += mission.reward_xp
    profile.level = level_for_xp(profile.xp)
    await credit(db, user_id, mission.reward_coins, "mission_reward", f"mission:{user_id}:{mission.id}")
    await db.commit()
    return {"ok": True, "reward_coins": mission.reward_coins, "reward_xp": mission.reward_xp, "level": profile.level}
