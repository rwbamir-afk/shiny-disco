"""Premium economy API. Telegram Stars fulfillment is provider-side only."""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..services.premium_service import gem_balance, battle_pass, claim_battle_pass_reward, unlock_premium_pass, vip_status, create_star_intent, fulfill_star_purchase, GEM_PACKS, VIP_STARS_30D
from ..config import get_settings

router = APIRouter(prefix="/premium", tags=["premium"])

class ProductIn(BaseModel):
    product: str

class RewardIn(BaseModel):
    level: int
    premium: bool = False

@router.get("/wallet")
async def premium_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"gems": await gem_balance(db, user.id)}

@router.get("/stars/catalog")
async def stars_catalog():
    return {"provider": "telegram_stars", "products": [*GEM_PACKS, {"product": "vip_30d", "stars": VIP_STARS_30D, "duration_days": 30}]}

@router.post("/stars/intent")
async def stars_intent(body: ProductIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await create_star_intent(db, user.id, body.product)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/battle-pass")
async def get_battle_pass(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await battle_pass(db, user.id)

@router.post("/battle-pass/unlock")
async def unlock_bp(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await unlock_premium_pass(db, user.id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))

@router.post("/battle-pass/claim")
async def claim_bp(body: RewardIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await claim_battle_pass_reward(db, user.id, body.level, body.premium)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))

@router.get("/vip")
async def get_vip(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await vip_status(db, user.id)


class FulfillIn(BaseModel):
    purchase_id: str
    provider_charge_id: str

@router.post("/internal/stars/fulfill")
async def fulfill(body: FulfillIn, x_hokm_payment_secret: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    secret = get_settings().telegram_payment_webhook_secret
    if not secret or x_hokm_payment_secret != secret:
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        return await fulfill_star_purchase(db, body.purchase_id, body.provider_charge_id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
