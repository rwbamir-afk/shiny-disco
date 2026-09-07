"""Hokm engine — typed game actions (validated commands)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .cards import Card, Suit


class ActionType(str, Enum):
    SELECT_TRUMP = "select_trump"
    PLAY_CARD = "play_card"


@dataclass(frozen=True)
class GameAction:
    """A validated, idempotent command against the engine.

    The engine only ever receives: the acting seat and a typed payload. It never
    trusts client-supplied state (cards, winners, scores, trump).
    """

    type: ActionType
    seat: int
    request_id: str
    card: Optional[Card] = None
    trump: Optional[Suit] = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required for idempotency")
