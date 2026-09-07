"""Standalone, dependency-free Hokm game engine.

Public API:
    HokmEngine — deterministic server-authoritative state machine.
    GameAction, ActionType — validated commands.
    Card, Suit, Rank — card domain model.
    InvalidActionError and friends — error hierarchy.
"""
from .actions import ActionType, GameAction
from .cards import ALL_SUITS, Card, Rank, Suit, build_deck
from .engine import HokmEngine, beats, next_seat
from .exceptions import (
    CardNotInHandError,
    HokmError,
    InvalidActionError,
    InvalidStateError,
    MustFollowSuitError,
    WrongTurnError,
)
from .models import GamePhase, GameState, PlayerState, Team, TrickState

__version__ = "0.1.0"
__all__ = [
    "ActionType",
    "GameAction",
    "Card",
    "Rank",
    "Suit",
    "build_deck",
    "HokmEngine",
    "beats",
    "next_seat",
    "HokmError",
    "InvalidActionError",
    "InvalidStateError",
    "CardNotInHandError",
    "WrongTurnError",
    "MustFollowSuitError",
    "GamePhase",
    "GameState",
    "PlayerState",
    "Team",
    "TrickState",
    "ALL_SUITS",
    "GameVariant",
    "VariantRules",
    "VariantHokmEngine",
]
from .variants import GameVariant, VariantRules, get_variant, require_playable, supported_variants
from .variant_engine import VariantHokmEngine
