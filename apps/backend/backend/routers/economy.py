"""Wallet, daily reward, shop and inventory API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..services.economy_service import balance, claim_daily, shop, inventory, buy, equip, ledger

router = APIRouter(prefix="/economy", tags=["economy"])

@router.get("/wallet")
async def wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"coins": await balance(db, user.id)}

@router.get("/ledger")
async def wallet_ledger(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"entries": await ledger(db, user.id)}

@router.post("/daily")
async def daily(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await claim_daily(db, user.id)
    await db.commit()
    return result

@router.get("/shop")
async def get_shop(db: AsyncSession = Depends(get_db)):
    return {"items": await shop(db)}

@router.get("/inventory")
async def get_inventory(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"items": await inventory(db, user.id)}

@router.post("/shop/{item_id}/buy")
async def purchase(item_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await buy(db, user.id, item_id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))

@router.post("/inventory/{item_id}/equip")
async def equip_item(item_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await equip(db, user.id, item_id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
