"""Pydantic contracts — the safe, client-visible API schema.

These are deliberately separate from the DB models and from the server-only
game snapshot. They define the boundary of what may be serialized to clients.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ auth
class TelegramAuthIn(BaseModel):
    init_data: str = Field(..., description="Telegram WebApp initData")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    telegram_id: int
    username: Optional[str] = None
    first_name: str = ""
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class ProfileOut(BaseModel):
    user_id: str
    display_name: str
    level: int
    xp: int
    rating: int
    games_played: int
    wins: int
    losses: int
    win_rate: float
    streak: int
    max_streak: int


class ProfileUpdateIn(BaseModel):
    bio: str = Field(default="", max_length=160)
    profile_title: str = Field(default="", max_length=64)


class SettingsUpdateIn(BaseModel):
    show_online: Optional[bool] = None
    allow_friend_requests: Optional[bool] = None
    public_profile: Optional[bool] = None
    notify_friend_requests: Optional[bool] = None
    notify_friend_accepts: Optional[bool] = None
    notify_rewards: Optional[bool] = None
    sound_enabled: Optional[bool] = None
    vibration_enabled: Optional[bool] = None
    compact_cards: Optional[bool] = None
    auto_sort_hand: Optional[bool] = None
    preferred_card_speed: Optional[str] = Field(default=None, pattern="^(slow|normal|fast)$")
    theme: Optional[str] = Field(default=None, max_length=32)
    language: Optional[str] = Field(default=None, pattern="^(fa|en)$")


class ProfileUpdateOut(BaseModel):
    bio: str
    profile_title: str


class AuthResponse(BaseModel):
    user: UserOut
    profile: ProfileOut
    tokens: TokenPair


# ------------------------------------------------------------------ rooms
class RoomOut(BaseModel):
    id: str
    creator_id: Optional[str] = None
    status: str
    invite_code: str
    rules_version: str
    players: list["RoomPlayerOut"] = []


class RoomPlayerOut(BaseModel):
    user_id: Optional[str] = None
    seat: int
    username: Optional[str] = None
    display_name: str = ""
    is_bot: bool = False
    ready: bool = False


class CreateRoomIn(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    is_multi_deal: bool = False


class JoinRoomIn(BaseModel):
    invite_code: str


class RoomReadyIn(BaseModel):
    ready: bool


# ------------------------------------------------------------------ matchmaking
class MatchmakingIn(BaseModel):
    mode: str = "quick"


class MatchmakingStatusOut(BaseModel):
    status: str  # searching | matched | no_game
    game_id: Optional[str] = None


# ------------------------------------------------------------------ game
class PlayerGameView(BaseModel):
    """The ONLY game state ever sent to a client (Section 11/32)."""

    game_id: str
    rules_version: str
    phase: str
    seat: int
    team: str
    hakem_seat: int
    trump: Optional[str] = None
    current_player: Optional[int] = None
    is_my_turn: bool = False
    hand: list[str] = []
    legal_cards: list[str] = []
    trick: dict[str, Any] = {}
    table: list[dict[str, Any]] = []
    scores: dict[str, int] = {}
    tricks_played: int = 0
    winner_team: Optional[str] = None
    # Operational fields added server-side (not derived from the engine).
    turn_deadline: Optional[int] = None
    timers: dict[str, Any] = Field(default_factory=dict)
    players: list[dict[str, Any]] = Field(default_factory=list)  # public player meta


class GameActionIn(BaseModel):
    type: str  # select_trump | play_card
    card: Optional[str] = None
    trump: Optional[str] = None
    request_id: str = Field(...)


class ResultOut(BaseModel):
    game_id: str
    winner_team: str
    scores: dict[str, int]
    rating_changes: dict[str, int]
    xp_changes: dict[str, int]
    coin_changes: dict[str, int] = {}
    game_stats: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------ rankings
class RankingEntry(BaseModel):
    user_id: str
    display_name: str
    rating: int
    games_played: int
    wins: int


# ------------------------------------------------------------------ reports
class ReportIn(BaseModel):
    reported_user_id: Optional[str] = None
    game_id: Optional[str] = None
    reason: str
    detail: str = ""


class ReportOut(BaseModel):
    id: str
    status: str
    reason: str


class MessageOut(BaseModel):
    ok: bool = True
    message: str = ""


class ErrorOut(BaseModel):
    ok: bool = False
    error: str
    code: str


class IdempotentResultOut(BaseModel):
    accepted: bool = True
    view: Optional[PlayerGameView] = None
