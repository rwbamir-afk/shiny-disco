"""User + profile services: create/update from Telegram, XP/level progression, and Elo rating."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserProfile, Wallet


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    res = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def get_profile(db: AsyncSession, user_id: str) -> UserProfile | None:
    res = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    return res.scalar_one_or_none()


async def upsert_user_from_telegram(
    db: AsyncSession, tg: dict, is_bot: bool = False, bot_difficulty: str | None = None
) -> User:
    """Create or update a user from verified Telegram init-data. Idempotent on telegram_id."""
    telegram_id = int(tg["id"])
    user = await get_user_by_telegram_id(db, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=tg.get("username"),
            first_name=tg.get("first_name", "بازیکن"),
            last_name=tg.get("last_name"),
            avatar_url=(tg.get("photo_url") or None),
            is_bot=is_bot,
            bot_difficulty=bot_difficulty,
        )
        db.add(user)
        await db.flush()
        db.add(UserProfile(user_id=user.id))
        db.add(Wallet(user_id=user.id, coins=0))
        await db.flush()
    else:
        if tg.get("username"):
            user.username = tg["username"]
        if tg.get("first_name"):
            user.first_name = tg["first_name"]
        if tg.get("last_name"):
            user.last_name = tg["last_name"]
        if tg.get("photo_url"):
            user.avatar_url = tg["photo_url"]
    return user


def bot_user_dict(telegram_id: int, difficulty: str) -> dict:
    return {"id": str(telegram_id), "first_name": f"ربات {difficulty}"}


# ---------------------------------------------------------------- XP / level
def xp_to_next_level(level: int) -> int:
    """XP required to advance from `level` to `level + 1`. Configurable, rebalanced later."""
    return 100 + (level - 1) * 25


def level_for_xp(xp: int) -> int:
    level = 1
    remaining = max(0, xp)
    while True:
        need = xp_to_next_level(level)
        if remaining >= need:
            remaining -= need
            level += 1
        else:
            break
    return level


def xp_into_level(xp: int, level: int) -> dict:
    """Progress within the current level for display."""
    base = 0
    for lvl in range(1, level):
        base += xp_to_next_level(lvl)
    need = xp_to_next_level(level)
    current = max(0, xp - base)
    return {"current": current, "target": need}


def xp_award_for_result(is_win: bool, streak: int) -> int:
    """XP for a completed game (win bonus + streak bonus). Server-calculated only."""
    base = 30 if is_win else 15
    streak_bonus = min(20, streak * 5) if is_win else 0
    return base + streak_bonus


def rank_tier(rating: int) -> dict:
    bands = [(1200, "شاه"), (1100, "وزیر"), (1000, "سردار"), (900, "سرباز"), (0, "نوآموز")]
    for minimum, title in bands:
        if rating >= minimum:
            return {"key": title, "title": title, "min_rating": minimum}
    return {"key": "نوآموز", "title": "نوآموز", "min_rating": 0}

# ---------------------------------------------------------------- rating (Elo)
def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def elo_update(ra: float, rb: float, score: float, k: float = 32.0) -> float:
    """New rating for a player with rating `ra` vs opponent average `rb`."""
    return ra + k * (score - expected_score(ra, rb))


def team_rating_change(player_rating: int, opponent_avg: int, won: bool, k: float = 32.0) -> int:
    """Delta for a player in a 2v2 team game. Elo, rounded, with a rating floor."""
    score = 1.0 if won else 0.0
    new = elo_update(float(player_rating), float(opponent_avg), score, k)
    return int(round(new - player_rating))


def opponent_avg_rating(ratings: list[int]) -> int:
    return int(round(sum(ratings) / len(ratings))) if ratings else 1000


def profile_public(profile: UserProfile, user: User) -> dict:
    won = profile.wins
    played = profile.games_played
    win_rate = (won / played * 100.0) if played else 0.0
    display_name = user.first_name or user.username or "کاربر"
    return {
        "user_id": profile.user_id,
        "display_name": display_name,
        "level": profile.level,
        "xp": profile.xp,
        "rating": profile.rating,
        "rank_tier": rank_tier(profile.rating),
        "games_played": played,
        "wins": won,
        "losses": profile.losses,
        "win_rate": round(win_rate, 1),
        "streak": profile.streak,
        "max_streak": profile.max_streak,
        "bio": profile.bio,
        "profile_title": profile.profile_title,
    }
