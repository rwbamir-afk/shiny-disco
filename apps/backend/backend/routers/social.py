"""Friends, blocks and in-app notifications."""
from __future__ import annotations
import json
from sqlalchemy import and_, or_, select, delete, func
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..deps import get_current_user
from ..models import User, UserProfile, FriendRequest, Friendship, UserBlock, Notification

router = APIRouter(prefix="/social", tags=["social"])


def user_public(u: User, profile: UserProfile | None = None) -> dict:
    last_seen = profile.last_seen if profile else None
    if last_seen is None:
        last_seen = None
    elif last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    online = bool(profile.show_online and last_seen and datetime.now(timezone.utc) - last_seen <= timedelta(seconds=90))
    return {"id": u.id, "username": u.username, "display_name": (u.first_name or u.username or "بازیکن"), "avatar_url": u.avatar_url, "online": online, "last_seen": last_seen.isoformat() if last_seen else None}

async def blocked(db, a: str, b: str) -> bool:
    q = select(UserBlock.id).where(or_(and_(UserBlock.blocker_id == a, UserBlock.blocked_id == b), and_(UserBlock.blocker_id == b, UserBlock.blocked_id == a)))
    return (await db.execute(q)).scalar_one_or_none() is not None

async def notify(db, user_id: str, kind: str, title: str, body: str, payload: dict | None = None):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    preference = {"friend_request": "notify_friend_requests", "friend_accepted": "notify_friend_accepts", "reward": "notify_rewards"}.get(kind)
    if profile is not None and preference and not getattr(profile, preference):
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, payload=json.dumps(payload or {}, ensure_ascii=False)))

@router.get("/search")
async def search(q: str = "", user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = q.strip()[:64]
    if len(q) < 2: return {"users": []}
    stmt = select(User).where(User.id != user.id, User.is_bot.is_(False), or_(User.username.ilike(f"%{q}%"), User.first_name.ilike(f"%{q}%"))).limit(20)
    rows = (await db.execute(stmt)).scalars().all()
    ids = [u.id for u in rows if not await blocked(db, user.id, u.id)]
    visible = [u for u in rows if u.id in ids]
    profiles = {} if not ids else {p.user_id: p for p in (await db.execute(select(UserProfile).where(UserProfile.user_id.in_(ids)))).scalars().all()}
    return {"users": [user_public(u, profiles.get(u.id)) for u in visible]}

@router.get("/friends")
async def friends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ids = (await db.execute(select(Friendship.friend_id).where(Friendship.user_id == user.id))).scalars().all()
    users = [] if not ids else (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    profiles = {} if not ids else {p.user_id: p for p in (await db.execute(select(UserProfile).where(UserProfile.user_id.in_(ids)))).scalars().all()}
    return {"friends": [user_public(u, profiles.get(u.id)) for u in users]}

@router.get("/requests")
async def requests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FriendRequest, User).join(User, User.id == FriendRequest.sender_id).where(FriendRequest.receiver_id == user.id, FriendRequest.status == "pending"))).all()
    ids = [u.id for _, u in rows]
    profiles = {} if not ids else {p.user_id: p for p in (await db.execute(select(UserProfile).where(UserProfile.user_id.in_(ids)))).scalars().all()}
    return {"requests": [{"id": r.id, "user": user_public(u, profiles.get(u.id))} for r, u in rows]}

@router.post("/requests/{target_id}")
async def send_request(target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if target_id == user.id: raise HTTPException(400, "cannot friend yourself")
    target = await db.get(User, target_id)
    if not target or target.is_blocked: raise HTTPException(404, "user not found")
    target_profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == target_id))).scalar_one_or_none()
    if target_profile is not None and not target_profile.allow_friend_requests:
        raise HTTPException(403, "friend requests disabled")
    if await blocked(db, user.id, target_id): raise HTTPException(403, "blocked")
    exists = (await db.execute(select(Friendship.id).where(Friendship.user_id == user.id, Friendship.friend_id == target_id))).scalar_one_or_none()
    if exists: return {"ok": True, "status": "friends"}
    reverse = (await db.execute(select(FriendRequest).where(FriendRequest.sender_id == target_id, FriendRequest.receiver_id == user.id, FriendRequest.status == "pending"))).scalar_one_or_none()
    if reverse:
        reverse.status = "accepted"
        db.add_all([Friendship(user_id=user.id, friend_id=target_id), Friendship(user_id=target_id, friend_id=user.id)])
        await notify(db, target_id, "friend_accepted", "درخواست دوستی پذیرفته شد", user.first_name or "یک بازیکن")
        await db.commit(); return {"ok": True, "status": "friends"}
    req = (await db.execute(select(FriendRequest).where(FriendRequest.sender_id == user.id, FriendRequest.receiver_id == target_id))).scalar_one_or_none()
    if req: req.status = "pending"
    else: db.add(FriendRequest(sender_id=user.id, receiver_id=target_id, status="pending"))
    await notify(db, target_id, "friend_request", "درخواست دوستی جدید", user.first_name or "یک بازیکن", {"user_id": user.id})
    await db.commit(); return {"ok": True, "status": "pending"}

@router.post("/requests/{request_id}/accept")
async def accept(request_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    req = await db.get(FriendRequest, request_id)
    if not req or req.receiver_id != user.id or req.status != "pending": raise HTTPException(404, "request not found")
    if await blocked(db, user.id, req.sender_id): raise HTTPException(403, "blocked")
    req.status = "accepted"
    db.add_all([Friendship(user_id=user.id, friend_id=req.sender_id), Friendship(user_id=req.sender_id, friend_id=user.id)])
    await notify(db, req.sender_id, "friend_accepted", "درخواست دوستی پذیرفته شد", user.first_name or "بازیکن")
    await db.commit(); return {"ok": True}

@router.post("/requests/{request_id}/reject")
async def reject(request_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    req = await db.get(FriendRequest, request_id)
    if not req or req.receiver_id != user.id: raise HTTPException(404, "request not found")
    req.status = "rejected"; await db.commit(); return {"ok": True}

@router.delete("/friends/{friend_id}")
async def remove_friend(friend_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Friendship).where(or_(and_(Friendship.user_id == user.id, Friendship.friend_id == friend_id), and_(Friendship.user_id == friend_id, Friendship.friend_id == user.id))))
    await db.commit(); return {"ok": True}

@router.post("/blocks/{target_id}")
async def block(target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if target_id == user.id: raise HTTPException(400, "cannot block yourself")
    if not await db.get(User, target_id): raise HTTPException(404, "user not found")
    if not await blocked(db, user.id, target_id): db.add(UserBlock(blocker_id=user.id, blocked_id=target_id))
    await db.execute(delete(Friendship).where(or_(and_(Friendship.user_id == user.id, Friendship.friend_id == target_id), and_(Friendship.user_id == target_id, Friendship.friend_id == user.id))))
    await db.commit(); return {"ok": True}

@router.delete("/blocks/{target_id}")
async def unblock(target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id)); await db.commit(); return {"ok": True}

@router.get("/notifications")
async def notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50))).scalars().all()
    unread = sum(1 for n in rows if not n.read)
    return {"unread": unread, "notifications": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "payload": json.loads(n.payload or "{}"), "read": n.read, "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]}

@router.post("/notifications/read-all")
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(Notification.__table__.update().where(Notification.user_id == user.id, Notification.read.is_(False)).values(read=True)); await db.commit(); return {"ok": True}


@router.get("/notifications/unread-count")
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = (await db.execute(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read.is_(False)))).scalar_one()
    return {"unread": int(count)}

@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    notice = await db.get(Notification, notification_id)
    if not notice or notice.user_id != user.id:
        raise HTTPException(404, "notification not found")
    notice.read = True
    await db.commit()
    return {"ok": True}

@router.get("/presence/{user_id}")
async def presence(user_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user_id == user.id:
        target = user
    else:
        target = await db.get(User, user_id)
    if not target or target.is_blocked or await blocked(db, user.id, user_id):
        raise HTTPException(404, "user not found")
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == target.id))).scalar_one_or_none()
    data = user_public(target, profile)
    return {"user_id": target.id, "online": data["online"], "last_seen": data["last_seen"]}

@router.get("/status")
async def social_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if profile:
        profile.last_seen = datetime.now(timezone.utc)
    friend_count = (await db.execute(select(func.count(Friendship.id)).where(Friendship.user_id == user.id))).scalar_one()
    pending = (await db.execute(select(func.count(FriendRequest.id)).where(FriendRequest.receiver_id == user.id, FriendRequest.status == "pending"))).scalar_one()
    unread = (await db.execute(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read.is_(False)))).scalar_one()
    await db.commit()
    return {"friends": int(friend_count), "pending_requests": int(pending), "unread_notifications": int(unread)}


@router.get("/outgoing-requests")
async def outgoing_requests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FriendRequest, User).join(User, User.id == FriendRequest.receiver_id).where(FriendRequest.sender_id == user.id, FriendRequest.status == "pending").order_by(FriendRequest.created_at.desc()))).all()
    return {"requests": [{"id": r.id, "user": user_public(u)} for r, u in rows]}

@router.get("/blocks")
async def blocks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(UserBlock, User).join(User, User.id == UserBlock.blocked_id).where(UserBlock.blocker_id == user.id).order_by(UserBlock.created_at.desc()))).all()
    return {"users": [user_public(u) for _, u in rows]}

@router.get("/relationship/{target_id}")
async def relationship(target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if target_id == user.id:
        return {"status": "self"}
    if not await db.get(User, target_id):
        raise HTTPException(404, "user not found")
    if await blocked(db, user.id, target_id):
        return {"status": "blocked"}
    if (await db.execute(select(Friendship.id).where(Friendship.user_id == user.id, Friendship.friend_id == target_id))).scalar_one_or_none():
        return {"status": "friends"}
    if (await db.execute(select(FriendRequest.id).where(FriendRequest.sender_id == user.id, FriendRequest.receiver_id == target_id, FriendRequest.status == "pending"))).scalar_one_or_none():
        return {"status": "outgoing_pending"}
    if (await db.execute(select(FriendRequest.id).where(FriendRequest.sender_id == target_id, FriendRequest.receiver_id == user.id, FriendRequest.status == "pending"))).scalar_one_or_none():
        return {"status": "incoming_pending"}
    return {"status": "none"}

@router.delete("/requests/{request_id}")
async def cancel_request(request_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    req = await db.get(FriendRequest, request_id)
    if not req or req.sender_id != user.id or req.status != "pending":
        raise HTTPException(404, "request not found")
    await db.delete(req)
    await db.commit()
    return {"ok": True}

@router.get("/notifications/page")
async def notifications_page(limit: int = 20, offset: int = 0, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    limit = min(max(limit, 1), 100); offset = max(offset, 0)
    rows = (await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {"offset": offset, "limit": limit, "has_more": len(rows) == limit, "notifications": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "payload": json.loads(n.payload or "{}"), "read": n.read, "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]}
