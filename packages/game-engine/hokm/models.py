"""
Hokm engine — domain model.

Defines the deterministic state machine for one complete game (one deal / match).
Zero infrastructure dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .cards import Card, Suit


class GamePhase(str, Enum):
    IDLE = "idle"
    DEALING = "dealing"
    TRUMP_SELECTION = "trump_selection"
    PLAYING = "playing"
    GAME_ENDED = "game_ended"


class Team(int, Enum):
    """Two fixed teams. TeamA = seats {0,2} (even), TeamB = seats {1,3} (odd)."""

    A = 0
    B = 1

    @property
    def name_fa(self) -> str:
        return "تیم شما" if self is Team.A else "تیم حریف"

    @staticmethod
    def seat_to_team(seat: int) -> "Team":
        return Team.A if seat % 2 == 0 else Team.B

    @staticmethod
    def partner_seat(seat: int) -> int:
        return (seat + 2) % 4


@dataclass
class PlayerState:
    """Server-side authoritative state for one seat."""

    seat: int
    hand: list[Card] = field(default_factory=list)
    team: Team = field(init=False)
    played_cards: list[Card] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.team = Team.seat_to_team(self.seat)

    def sort_hand(self) -> None:
        self.hand.sort()


@dataclass
class TrickState:
    """One 'trick' (a round of up to 4 card plays)."""

    leader_seat: int
    plays: list[tuple[int, Card]] = field(default_factory=list)
    winner_seat: Optional[int] = None
    winning_card: Optional[Card] = None

    @property
    def led_suit(self) -> Optional[Suit]:
        if not self.plays:
            return None
        return self.plays[0][1].suit

    @property
    def complete(self) -> bool:
        return len(self.plays) == 4


@dataclass
class RoundState:
    """One round = one deal. As of hokm-v1 the MVP match is exactly one round."""

    number: int = 1
    hakem_seat: int = 0
    trump: Optional[Suit] = None
    leader_seat: Optional[int] = None
    tricks: list[TrickState] = field(default_factory=list)
    won_tricks: dict[Team, int] = field(default_factory=lambda: {Team.A: 0, Team.B: 0})
    winner_team: Optional[Team] = None

    @property
    def tricks_won(self) -> int:
        return len([t for t in self.tricks if t.complete and t.winner_seat is not None])

    def current_trick(self) -> Optional[TrickState]:
        if self.tricks and not self.tricks[-1].complete:
            return self.tricks[-1]
        return None


@dataclass
class GameState:
    """Authoritative, private game state. Never sent to clients directly."""

    phase: GamePhase = GamePhase.IDLE
    rules_version: str = "hokm-v1"
    players: list[PlayerState] = field(default_factory=lambda: [PlayerState(s) for s in range(4)])
    round: RoundState = field(default_factory=RoundState)
    seed: int = 0
    created_at: str = ""
    _rng: object = field(default=None, repr=False)  # engine-internal, never serialised

    @property
    def num_players(self) -> int:
        return 4

    def player(self, seat: int) -> PlayerState:
        return self.players[seat]
