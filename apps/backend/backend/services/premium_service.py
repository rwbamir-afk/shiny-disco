"""Premium economy primitives: gems, seasonal battle pass, VIP and Telegram Stars intents.

Telegram Stars payment is intentionally split into intent creation and provider-side fulfillment.
A client can never mark an intent paid; the Telegram Bot API webhook/service must fulfill it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import PremiumWallet, GemLedger, BattlePassSeason, UserBattlePass, VipSubscription, StarPurchaseIntent, gen_uuid

GEM_PACKS = (
    {"product": "gems_100", "stars": 10, "gems": 100},
    {"product": "gems_550", "stars": 50, "gems": 550},
    {"product": "gems_1200", "stars": 100, "gems": 1200},
    {"product": "gems_3000", "stars": 250, "gems": 3000},
)
BATTLE_PASS_REWARDS = {
    1: {"free_coins": 100, "premium_gems": 40},
    5: {"free_coins": 250, "premium_gems": 60},
    10: {"free_coins": 500, "premium_gems": 100},
    15: {"free_coins": 750, "premium_gems": 140},
    20: {"free_coins": 1000, "premium_gems": 180},
    25: {"free_coins": 1500, "premium_gems": 220},
    30: {"free_coins": 3000, "premium_gems": 400},
}
VIP_STARS_30D = 300

async def ensure_premium_wallet(db: AsyncSession, user_id: str) -> PremiumWallet:
    wallet = (await db.execute(select(PremiumWallet).where(PremiumWallet.user_id == user_id))).scalar_one_or_none()
    if wallet is None:
        wallet = PremiumWallet(user_id=user_id, gems=0)
        db.add(wallet)
        await db.flush()
    return wallet

async def gem_balance(db: AsyncSession, user_id: str) -> int:
    return (await ensure_premium_wallet(db, user_id)).gems

async def change_gems(db: AsyncSession, user_id: str, amount: int, reason: str, key: str, metadata: dict | None = None) -> GemLedger:
    if amount == 0:
        raise ValueError("amount must not be zero")
    existing = (await db.execute(select(GemLedger).where(GemLedger.user_id == user_id, GemLedger.idempotency_key == key))).scalar_one_or_none()
    if existing:
        return existing
    wallet = await ensure_premium_wallet(db, user_id)
    new_balance = wallet.gems + amount
    if new_balance < 0:
        raise ValueError("insufficient gems")
    wallet.gems = new_balance
    row = GemLedger(user_id=user_id, amount=amount, balance_after=new_balance, reason=reason, idempotency_key=key, metadata_json=json.dumps(metadata or {}))
    db.add(row)
    await db.flush()
    return row

async def ensure_active_season(db: AsyncSession) -> BattlePassSeason:
    now = datetime.now(timezone.utc)
    season = (await db.execute(select(BattlePassSeason).where(BattlePassSeason.active.is_(True), BattlePassSeason.starts_at <= now, BattlePassSeason.ends_at > now).order_by(BattlePassSeason.ends_at.desc()))).scalars().first()
    if season:
        return season
    starts = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    next_month = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1, tzinfo=timezone.utc)
    season = BattlePassSeason(slug=f"season-{starts:%Y-%m}", title=f"فصل {starts:%Y/%m}", starts_at=starts, ends_at=next_month, max_level=30, premium_price_gems=800, active=True)
    db.add(season)
    await db.flush()
    return season

def xp_for_level(level: int) -> int:
    return max(100, level * 100)

async def battle_pass(db: AsyncSession, user_id: str) -> dict:
    season = await ensure_active_season(db)
    bp = (await db.execute(select(UserBattlePass).where(UserBattlePass.user_id == user_id, UserBattlePass.season_id == season.id))).scalar_one_or_none()
    if bp is None:
        bp = UserBattlePass(user_id=user_id, season_id=season.id, xp=0, level=1, premium=False)
        db.add(bp)
        await db.flush()
    free_claimed = json.loads(bp.claimed_free or "[]")
    premium_claimed = json.loads(bp.claimed_premium or "[]")
    return {"season": {"id": season.id, "slug": season.slug, "title": season.title, "starts_at": season.starts_at.isoformat(), "ends_at": season.ends_at.isoformat(), "max_level": season.max_level, "premium_price_gems": season.premium_price_gems}, "pass": {"xp": bp.xp, "level": bp.level, "premium": bp.premium, "claimed_free": free_claimed, "claimed_premium": premium_claimed}, "rewards": [{"level": i, **BATTLE_PASS_REWARDS.get(i, {"free_coins": 50 + i * 10, "premium_gems": 10 + i * 2})} for i in range(1, season.max_level + 1)]}

async def add_battle_pass_xp(db: AsyncSession, user_id: str, amount: int, key: str) -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")
    # Reuse the gem ledger as the idempotency store only for this explicit BP key would be wrong.
    # XP grants are game-event driven and should be keyed by a GameEvent in production; this helper
    # deliberately remains a pure mutation primitive.
    season = await ensure_active_season(db)
    bp = (await db.execute(select(UserBattlePass).where(UserBattlePass.user_id == user_id, UserBattlePass.season_id == season.id))).scalar_one_or_none()
    if bp is None:
        bp = UserBattlePass(user_id=user_id, season_id=season.id, xp=0, level=1)
        db.add(bp)
        await db.flush()
    bp.xp += amount
    while bp.level < season.max_level and bp.xp >= xp_for_level(bp.level):
        bp.xp -= xp_for_level(bp.level)
        bp.level += 1
    await db.flush()
    return {"level": bp.level, "xp": bp.xp, "max_level": season.max_level}

async def claim_battle_pass_reward(db: AsyncSession, user_id: str, level: int, premium: bool) -> dict:
    season = await ensure_active_season(db)
    bp = (await db.execute(select(UserBattlePass).where(UserBattlePass.user_id == user_id, UserBattlePass.season_id == season.id))).scalar_one_or_none()
    if not bp or level < 1 or level > bp.level:
        raise ValueError("reward not unlocked")
    if premium and not bp.premium:
        raise ValueError("premium pass required")
    field = "claimed_premium" if premium else "claimed_free"
    claimed = json.loads(getattr(bp, field) or "[]")
    if level in claimed:
        raise ValueError("reward already claimed")
    reward = BATTLE_PASS_REWARDS.get(level, {"free_coins": 50 + level * 10, "premium_gems": 10 + level * 2})
    if premium:
        await change_gems(db, user_id, reward["premium_gems"], "battle_pass_reward", f"bp-reward:{season.id}:{user_id}:p:{level}")
    else:
        from .economy_service import credit
        await credit(db, user_id, reward["free_coins"], "battle_pass_reward", f"bp-reward:{season.id}:{user_id}:f:{level}")
    claimed.append(level)
    setattr(bp, field, json.dumps(sorted(claimed)))
    await db.commit()
    return {"ok": True, "level": level, "premium": premium, "reward": reward}

async def unlock_premium_pass(db: AsyncSession, user_id: str) -> dict:
    season = await ensure_active_season(db)
    bp = (await db.execute(select(UserBattlePass).where(UserBattlePass.user_id == user_id, UserBattlePass.season_id == season.id))).scalar_one_or_none()
    if bp is None:
        bp = UserBattlePass(user_id=user_id, season_id=season.id, xp=0, level=1)
        db.add(bp)
        await db.flush()
    if bp.premium:
        return {"ok": True, "premium": True, "already_owned": True}
    await change_gems(db, user_id, -season.premium_price_gems, "battle_pass_unlock", f"bp-unlock:{season.id}:{user_id}")
    bp.premium = True
    await db.commit()
    return {"ok": True, "premium": True, "already_owned": False}

async def vip_status(db: AsyncSession, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    sub = (await db.execute(select(VipSubscription).where(VipSubscription.user_id == user_id, VipSubscription.active.is_(True), VipSubscription.ends_at > now).order_by(VipSubscription.ends_at.desc()))).scalars().first()
    return {"active": bool(sub), "tier": sub.tier if sub else None, "ends_at": sub.ends_at.isoformat() if sub else None}

async def create_star_intent(db: AsyncSession, user_id: str, product: str) -> dict:
    pack = next((x for x in GEM_PACKS if x["product"] == product), None)
    if pack is None and product == "vip_30d":
        pack = {"product": product, "stars": VIP_STARS_30D}
    if pack is None:
        raise ValueError("unknown product")
    payload = f"hokm:{gen_uuid()}"
    row = StarPurchaseIntent(user_id=user_id, product=product, stars=pack["stars"], payload=payload, status="pending")
    db.add(row)
    await db.commit()
    return {"id": row.id, "product": product, "stars": pack["stars"], "payload": payload, "status": "pending", "provider": "telegram_stars"}

async def fulfill_star_purchase(db: AsyncSession, purchase_id: str, provider_charge_id: str) -> dict:
    row = await db.get(StarPurchaseIntent, purchase_id)
    if not row:
        raise ValueError("purchase not found")
    if row.status == "paid":
        return {"ok": True, "status": "paid", "duplicate": True}
    if row.status != "pending":
        raise ValueError("purchase is not pending")
    row.status = "paid"
    row.provider_charge_id = provider_charge_id
    if row.product.startswith("gems_"):
        pack = next(x for x in GEM_PACKS if x["product"] == row.product)
        await change_gems(db, row.user_id, pack["gems"], "telegram_stars_purchase", f"stars:{row.id}", {"purchase_id": row.id, "stars": row.stars})
    elif row.product == "vip_30d":
        now = datetime.now(timezone.utc)
        existing = (await db.execute(select(VipSubscription).where(VipSubscription.user_id == row.user_id, VipSubscription.active.is_(True), VipSubscription.ends_at > now).order_by(VipSubscription.ends_at.desc()))).scalars().first()
        start = existing.ends_at if existing else now
        sub = VipSubscription(user_id=row.user_id, tier="vip", starts_at=start, ends_at=start + timedelta(days=30), source="stars", active=True)
        db.add(sub)
    await db.commit()
    return {"ok": True, "status": "paid", "product": row.product}
