"""
Hokm engine — core card model.

This module is part of the dependency-free game engine. It must never import
Telegram, HTTP, database, or framework modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    """The four French suits used by Hokm."""

    SPADES = "spades"
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"

    @property
    def symbol(self) -> str:
        return _SUIT_SYMBOLS[self]

    @property
    def index(self) -> int:
        return _SUIT_ORDER[self]


# Display unicode symbols and a fixed internal ordering (RTL-safe, no implied strength).
_SUIT_SYMBOLS = {
    Suit.SPADES: "\u2660",
    Suit.HEARTS: "\u2665",
    Suit.DIAMONDS: "\u2666",
    Suit.CLUBS: "\u2663",
}
_SUIT_ORDER = {
    Suit.SPADES: 0,
    Suit.HEARTS: 1,
    Suit.DIAMONDS: 2,
    Suit.CLUBS: 3,
}

ALL_SUITS = tuple(Suit)


class Rank(int, Enum):
    """Rank values 2..14 (J=11, Q=12, K=13, A=14). Higher wins."""

    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def label(self) -> str:
        return _RANK_LABELS[self]


_RANK_LABELS = {
    Rank.TWO: "2",
    Rank.THREE: "3",
    Rank.FOUR: "4",
    Rank.FIVE: "5",
    Rank.SIX: "6",
    Rank.SEVEN: "7",
    Rank.EIGHT: "8",
    Rank.NINE: "9",
    Rank.TEN: "10",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
}


@dataclass(frozen=True)
class Card:
    """A single immutable playing card."""

    suit: Suit
    rank: Rank

    def __post_init__(self) -> None:
        # Normalise inputs so `Card(Suit.HEARTS, "A")` works as well as `Card(Suit.HEARTS, Rank.ACE)`.
        if not isinstance(self.suit, Suit):
            raise TypeError("card suit must be a Suit")
        if not isinstance(self.rank, Rank):
            raise TypeError("card rank must be a Rank")

    @property
    def id(self) -> str:
        """Compact unique id, e.g. 'sA', 'h10'."""
        return f"{self.suit.value[0]}{self.rank.label}"

    @property
    def score_value(self) -> int:
        return int(self.rank)

    def __str__(self) -> str:
        return f"{self.rank.label}{self.suit.symbol}"

    def __lt__(self, other: "Card") -> bool:
        """Sort by suit index then rank value (for deterministic display/ordering)."""
        if self.suit.index != other.suit.index:
            return self.suit.index < other.suit.index
        return int(self.rank) < int(other.rank)

    def __repr__(self) -> str:
        return f"Card({self.suit.value!r}, {self.rank.name})"


def build_deck() -> list[Card]:
    """Return the standard 52-card deck (no jokers), deterministic order."""
    return [Card(suit, rank) for suit in ALL_SUITS for rank in Rank]
