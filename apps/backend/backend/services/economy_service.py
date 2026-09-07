"""Atomic coin wallet, daily rewards, shop and inventory services."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Wallet, WalletLedger, CosmeticItem, InventoryItem, DailyClaim

DAILY_REWARDS = (50, 75, 100, 125, 150, 200, 300)
SHOP_SEEDS = [
    ("table_girih", "میز گره‌چینی", "table", "میز با نقش هندسی ایرانی", 500, "rare", "table.girih"),
    ("card_turquoise", "دسته فیروزه", "card_back", "پشت کارت با الهام از فیروزه", 350, "common", "card.turquoise"),
    ("avatar_lion", "نشان شیر", "avatar_frame", "قاب شیر و خورشیدِ انتزاعی", 700, "epic", "frame.lion"),
    ("emote_saffron", "تعظیم زرین", "emote", "ایموت مخصوص پایان دست", 250, "common", "emote.saffron"),
    ("table_night", "شب یلدا", "table", "تم تیره با حال‌وهوای یلدا", 900, "epic", "table.yalda"),
    ("card_miniature", "مینیاتور ایرانی", "card_back", "نقش الهام‌گرفته از نگارگری ایرانی", 1200, "legendary", "card.miniature"),
]

async def ensure_shop_catalog(db: AsyncSession) -> None:
    for slug, name, category, description, price, rarity, asset_key in SHOP_SEEDS:
        row = (await db.execute(select(CosmeticItem).where(CosmeticItem.slug == slug))).scalar_one_or_none()
        if not row:
            db.add(CosmeticItem(slug=slug, name=name, category=category, description=description, price_coins=price, rarity=rarity, asset_key=asset_key))
    await db.flush()

async def ensure_wallet(db: AsyncSession, user_id: str) -> Wallet:
    wallet = (await db.execute(select(Wallet).where(Wallet.user_id == user_id))).scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(user_id=user_id, coins=0)
        db.add(wallet)
        await db.flush()
    return wallet

async def balance(db: AsyncSession, user_id: str) -> int:
    return (await ensure_wallet(db, user_id)).coins

async def credit(db: AsyncSession, user_id: str, amount: int, reason: str, key: str, metadata: dict | None = None) -> WalletLedger:
    if amount <= 0:
        raise ValueError("amount must be positive")
    existing = (await db.execute(select(WalletLedger).where(WalletLedger.user_id == user_id, WalletLedger.idempotency_key == key))).scalar_one_or_none()
    if existing:
        return existing
    wallet = await ensure_wallet(db, user_id)
    wallet.coins += amount
    row = WalletLedger(user_id=user_id, amount=amount, balance_after=wallet.coins, reason=reason, idempotency_key=key, metadata_json=json.dumps(metadata or {}))
    db.add(row)
    await db.flush()
    return row

async def debit(db: AsyncSession, user_id: str, amount: int, reason: str, key: str, metadata: dict | None = None) -> WalletLedger:
    if amount <= 0:
        raise ValueError("amount must be positive")
    existing = (await db.execute(select(WalletLedger).where(WalletLedger.user_id == user_id, WalletLedger.idempotency_key == key))).scalar_one_or_none()
    if existing:
        return existing
    wallet = await ensure_wallet(db, user_id)
    if wallet.coins < amount:
        raise ValueError("insufficient coins")
    wallet.coins -= amount
    row = WalletLedger(user_id=user_id, amount=-amount, balance_after=wallet.coins, reason=reason, idempotency_key=key, metadata_json=json.dumps(metadata or {}))
    db.add(row)
    await db.flush()
    return row

async def claim_daily(db: AsyncSession, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    existing = (await db.execute(select(DailyClaim).where(DailyClaim.user_id == user_id, DailyClaim.claim_date == today))).scalar_one_or_none()
    if existing:
        return {"claimed": False, "streak_day": existing.streak_day, "reward_coins": existing.reward_coins, "claim_date": today}
    previous = (await db.execute(select(DailyClaim).where(DailyClaim.user_id == user_id).order_by(DailyClaim.claim_date.desc()))).scalars().first()
    try:
        prev_date = datetime.fromisoformat(previous.claim_date).date() if previous else None
    except ValueError:
        prev_date = None
    streak = (previous.streak_day + 1) if previous and prev_date == now.date() - timedelta(days=1) else 1
    streak = min(streak, 7)
    reward = DAILY_REWARDS[streak - 1]
    db.add(DailyClaim(user_id=user_id, claim_date=today, streak_day=streak, reward_coins=reward))
    await credit(db, user_id, reward, "daily_reward", f"daily:{user_id}:{today}", {"streak_day": streak})
    return {"claimed": True, "streak_day": streak, "reward_coins": reward, "claim_date": today}

async def shop(db: AsyncSession) -> list[dict]:
    await ensure_shop_catalog(db)
    rows = (await db.execute(select(CosmeticItem).where(CosmeticItem.enabled.is_(True)).order_by(CosmeticItem.price_coins, CosmeticItem.name))).scalars().all()
    return [item_dict(x) for x in rows]

def item_dict(x: CosmeticItem) -> dict:
    return {"id": x.id, "slug": x.slug, "name": x.name, "category": x.category, "description": x.description, "price_coins": x.price_coins, "rarity": x.rarity, "asset_key": x.asset_key}

async def inventory(db: AsyncSession, user_id: str) -> list[dict]:
    rows = (await db.execute(select(InventoryItem, CosmeticItem).join(CosmeticItem, InventoryItem.item_id == CosmeticItem.id).where(InventoryItem.user_id == user_id).order_by(CosmeticItem.category, CosmeticItem.name))).all()
    return [{**item_dict(item), "inventory_id": inv.id, "equipped": inv.equipped} for inv, item in rows]

async def buy(db: AsyncSession, user_id: str, item_id: str) -> dict:
    item = await db.get(CosmeticItem, item_id)
    if not item or not item.enabled:
        raise ValueError("item not found")
    owned = (await db.execute(select(InventoryItem).where(InventoryItem.user_id == user_id, InventoryItem.item_id == item_id))).scalar_one_or_none()
    if owned:
        raise ValueError("item already owned")
    await debit(db, user_id, item.price_coins, "shop_purchase", f"purchase:{user_id}:{item_id}", {"item_id": item_id})
    inv = InventoryItem(user_id=user_id, item_id=item_id, equipped=False)
    db.add(inv)
    await db.commit()
    return {"ok": True, "item": item_dict(item)}

async def equip(db: AsyncSession, user_id: str, item_id: str) -> dict:
    inv = (await db.execute(select(InventoryItem).where(InventoryItem.user_id == user_id, InventoryItem.item_id == item_id))).scalar_one_or_none()
    if not inv:
        raise ValueError("item not owned")
    item = await db.get(CosmeticItem, item_id)
    if not item:
        raise ValueError("item not found")
    await db.execute(update(InventoryItem).where(InventoryItem.user_id == user_id, InventoryItem.item_id.in_(select(CosmeticItem.id).where(CosmeticItem.category == item.category))).values(equipped=False))
    inv.equipped = True
    await db.commit()
    return {"ok": True, "item_id": item_id, "category": item.category}

async def ledger(db: AsyncSession, user_id: str, limit: int = 50) -> list[dict]:
    rows = (await db.execute(select(WalletLedger).where(WalletLedger.user_id == user_id).order_by(WalletLedger.created_at.desc()).limit(min(limit, 100)))).scalars().all()
    return [{"id": r.id, "amount": r.amount, "balance_after": r.balance_after, "reason": r.reason, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]
