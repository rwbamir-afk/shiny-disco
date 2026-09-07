"""SQLAlchemy ORM models (Section 19 of the spec).

PostgreSQL is the production target. The same models run on SQLite for dev/tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def gen_uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str] = mapped_column(String(64), default="")
    last_name: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_difficulty: Mapped[str | None] = mapped_column(String(16))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    max_streak: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=1000)
    peak_rating: Mapped[int] = mapped_column(Integer, default=1000)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bio: Mapped[str] = mapped_column(Text, default="")
    profile_title: Mapped[str] = mapped_column(String(64), default="")
    show_online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_friend_requests: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public_profile: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_friend_requests: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_friend_accepts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_rewards: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    vibration_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    compact_cards: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_sort_hand: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    preferred_card_speed: Mapped[str] = mapped_column(String(16), default="normal")
    theme: Mapped[str] = mapped_column(String(32), default="iranian")
    language: Mapped[str] = mapped_column(String(8), default="fa")

    user: Mapped["User"] = relationship(back_populates="profile")


class RefreshSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(SAEnum("created", "waiting", "ready", "starting", "ingame", "closed", name="room_status"), default="waiting")
    config: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(32), default="hokm-v1")

    players: Mapped[list["RoomPlayer"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class RoomPlayer(Base):
    __tablename__ = "room_players"
    __table_args__ = (UniqueConstraint("room_id", "seat", name="uq_room_seat"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="players")


class Game(Base, TimestampMixin):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("waiting", "playing", "finished", "aborted", name="game_status"), default="waiting"
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    winner_team: Mapped[str | None] = mapped_column(String(8))
    final_scores: Mapped[str] = mapped_column(Text, default="{}")  # JSON {"A": int, "B": int}
    config: Mapped[str] = mapped_column(Text, default="{}")
    rules_version: Mapped[str] = mapped_column(String(32), default="hokm-v1")
    seed: Mapped[int] = mapped_column(BigInteger, default=0)
    snapshot: Mapped[str | None] = mapped_column(Text)  # server-side authoritative snapshot
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aborted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fairness_commitment: Mapped[str | None] = mapped_column(String(64))
    fairness_nonce: Mapped[str | None] = mapped_column(String(64))
    tournament_match_id: Mapped[str | None] = mapped_column(String(32), index=True)

    players: Mapped[list["GamePlayer"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (UniqueConstraint("game_id", "seat", name="uq_game_seat"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str] = mapped_column(String(8), nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_difficulty: Mapped[str | None] = mapped_column(String(16))
    connection_state: Mapped[str] = mapped_column(
        SAEnum("connected", "disconnected", "reconnecting", "bot_controlled", "finished", name="conn_state"),
        default="connected",
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    game: Mapped["Game"] = relationship(back_populates="players")


class Move(Base):
    """Append-only move/event log (Section 9). Used for replay, debugging, anti-cheat."""

    __tablename__ = "moves"
    __table_args__ = (Index("ix_moves_game_order", "game_id", "move_number"), UniqueConstraint("game_id", "request_id", name="uq_game_request"))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False)
    move_number: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[str | None] = mapped_column(String(32))
    seat: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    card: Mapped[str | None] = mapped_column(String(8))
    trump: Mapped[str | None] = mapped_column(String(16))
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    server_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSpectator(Base, TimestampMixin):
    __tablename__ = "game_spectators"
    __table_args__ = (UniqueConstraint("game_id", "user_id", name="uq_game_spectator"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameEvent(Base):
    """High-level game events for observability and future replay."""

    __tablename__ = "game_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    reporter_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    reported_user_id: Mapped[str | None] = mapped_column(String(32), index=True)
    game_id: Mapped[str | None] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(SAEnum("open", "reviewing", "resolved", "dismissed", name="report_status"), default="open")
    resolved_by: Mapped[str | None] = mapped_column(String(32))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    actor_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_idempotency"), Index("ix_wallet_ledger_user_created", "user_id", "created_at"))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PremiumWallet(Base, TimestampMixin):
    __tablename__ = "premium_wallets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    gems: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class GemLedger(Base):
    __tablename__ = "gem_ledger"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_gem_idempotency"), Index("ix_gem_ledger_user_created", "user_id", "created_at"))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BattlePassSeason(Base, TimestampMixin):
    __tablename__ = "battle_pass_seasons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_level: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    premium_price_gems: Mapped[int] = mapped_column(BigInteger, default=800, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserBattlePass(Base, TimestampMixin):
    __tablename__ = "user_battle_passes"
    __table_args__ = (UniqueConstraint("user_id", "season_id", name="uq_user_battle_pass"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    season_id: Mapped[str] = mapped_column(ForeignKey("battle_pass_seasons.id", ondelete="CASCADE"), nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    claimed_free: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    claimed_premium: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class VipSubscription(Base, TimestampMixin):
    __tablename__ = "vip_subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(16), default="vip", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="stars", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StarPurchaseIntent(Base, TimestampMixin):
    __tablename__ = "star_purchase_intents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    product: Mapped[str] = mapped_column(String(64), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    provider_charge_id: Mapped[str | None] = mapped_column(String(128))


class CosmeticItem(Base, TimestampMixin):
    __tablename__ = "cosmetic_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    price_coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), default="common")
    asset_key: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    item_id: Mapped[str] = mapped_column(ForeignKey("cosmetic_items.id", ondelete="CASCADE"), index=True, nullable=False)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DailyClaim(Base):
    __tablename__ = "daily_claims"
    __table_args__ = (UniqueConstraint("user_id", "claim_date", name="uq_daily_user_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    claim_date: Mapped[str] = mapped_column(String(10), nullable=False)
    streak_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mission(Base, TimestampMixin):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserMission(Base, TimestampMixin):
    __tablename__ = "user_missions"
    __table_args__ = (UniqueConstraint("user_id", "mission_id", name="uq_user_mission"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Achievement(Base, TimestampMixin):
    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    achievement_id: Mapped[str] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"), index=True, nullable=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FriendRequest(Base, TimestampMixin):
    __tablename__ = "friend_requests"
    __table_args__ = (UniqueConstraint("sender_id", "receiver_id", name="uq_friend_request_pair"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    receiver_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    friend_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    blocker_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    blocked_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[str] = mapped_column(Text, default="{}")
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = [
    "Base",
    "FriendRequest", "Friendship", "UserBlock", "Notification",
    "Wallet", "WalletLedger", "CosmeticItem", "InventoryItem", "DailyClaim", "Mission", "UserMission", "Achievement", "UserAchievement",
    "User",
    "UserProfile",
    "RefreshSession",
    "Room",
    "RoomPlayer",
    "Game",
    "GamePlayer",
    "Move",
    "GameSpectator",
    "GameEvent",
    "Report",
    "AuditLog",
]

class Club(Base, TimestampMixin):
    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    tag: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(240), default="")
    privacy: Mapped[str] = mapped_column(SAEnum("open", "invite", "closed", name="club_privacy"), default="open")
    max_members: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class ClubMember(Base, TimestampMixin):
    __tablename__ = "club_members"
    __table_args__ = (UniqueConstraint("club_id", "user_id", name="uq_club_member"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    club_id: Mapped[str] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(SAEnum("owner", "officer", "member", name="club_role"), default="member")
    contribution_xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class ClubJoinRequest(Base, TimestampMixin):
    __tablename__ = "club_join_requests"
    __table_args__ = (UniqueConstraint("club_id", "user_id", name="uq_club_join_request"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    club_id: Mapped[str] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(SAEnum("pending", "accepted", "rejected", "cancelled", name="club_request_status"), default="pending")


class Tournament(Base, TimestampMixin):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    bracket_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(SAEnum("registration", "running", "finished", "cancelled", name="tournament_status"), default="registration")
    entry_fee: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    prize_coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(32), default="hokm-v1")
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class TournamentParticipant(Base, TimestampMixin):
    __tablename__ = "tournament_participants"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id", name="uq_tournament_participant"), UniqueConstraint("tournament_id", "seed", name="uq_tournament_seed"))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    eliminated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TournamentMatch(Base, TimestampMixin):
    __tablename__ = "tournament_matches"
    __table_args__ = (UniqueConstraint("tournament_id", "round_no", "slot", name="uq_tournament_match_slot"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), index=True, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    player_a_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    player_b_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    player_c_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    player_d_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    game_id: Mapped[str | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(SAEnum("pending", "ready", "playing", "finished", "bye", "forfeit", name="tournament_match_status"), default="pending")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
