"""
Hokm engine — deterministic state machine and safe view projection.

This is the single source of truth for gameplay rules. It has NO dependency on
Telegram, HTTP, WebSocket, or a database. Deterministic given a seed.

Lifecycle (hokm-v1):  idle -> dealing -> trump_selection -> playing -> game_ended
"""
from __future__ import annotations

import random
from typing import Optional

from .actions import ActionType, GameAction
from .cards import ALL_SUITS, Card, Suit, build_deck
from .exceptions import (
    CardNotInHandError,
    InvalidActionError,
    MustFollowSuitError,
    WrongTurnError,
)
from .models import GamePhase, GameState, PlayerState, Team, TrickState

NUM_PLAYERS = 4
CARDS_PER_PLAYER = 13
TRICKS_PER_ROUND = CARDS_PER_PLAYER


def next_seat(seat: int) -> int:
    """Fixed cyclic play order (rendered clockwise). Deterministic."""
    return (seat + 1) % NUM_PLAYERS


def beats(candidate: Card, current: Card, led_suit: Suit, trump: Suit) -> bool:
    """Return True if `candidate` beats `current` in the trick."""
    # Trump beats everything non-trump.
    if candidate.suit == trump and current.suit != trump:
        return True
    if candidate.suit != trump and current.suit == trump:
        return False
    # Same suit -> higher rank wins.
    if candidate.suit == current.suit:
        return candidate.score_value > current.score_value
    # Different non-trump suits: only the led suit can win.
    if candidate.suit == led_suit and current.suit != led_suit:
        return True
    if candidate.suit != led_suit and current.suit == led_suit:
        return False
    # Both off-suit and non-trump (can only occur in impossible states) -> no win.
    return False


class HokmEngine:
    """Server-authoritative Hokm game state machine.

    Interact via `apply(action)`. The engine rejects any illegal action and
    leaves state unchanged if the action is invalid.
    """

    def __init__(self, seed: int = 0, rules_version: str = "hokm-v1") -> None:
        self._rng = random.Random(seed)
        self.state = GameState(seed=seed, rules_version=rules_version)
        self.state._rng = self._rng
        self._turn_seat: Optional[int] = None
        self._applied_request_ids: set[str] = set()

    # ------------------------------------------------------------------ setup
    def start(self) -> GameState:
        """Begin a new match: pick hakem and deal."""
        self.state.phase = GamePhase.DEALING
        self.state.round.hakem_seat = self._rng.randrange(NUM_PLAYERS)
        self._deal()
        self.state.phase = GamePhase.TRUMP_SELECTION
        return self.state

    def _deal(self) -> None:
        deck = build_deck()
        self._rng.shuffle(deck)
        for seat in range(NUM_PLAYERS):
            self.state.players[seat].hand = sorted(deck[seat * CARDS_PER_PLAYER : (seat + 1) * CARDS_PER_PLAYER])

    # ----------------------------------------------------------------- queries
    @property
    def phase(self) -> GamePhase:
        return self.state.phase

    @property
    def hakem_seat(self) -> int:
        return self.state.round.hakem_seat

    @property
    def trump(self) -> Optional[Suit]:
        return self.state.round.trump

    def current_player_seat(self) -> Optional[int]:
        return self._turn_seat

    def hand(self, seat: int) -> list[Card]:
        return self.state.player(seat).hand

    def legal_cards(self, seat: int) -> list[Card]:
        """The subset of the seat's hand that is legal to play right now."""
        if self.state.phase != GamePhase.PLAYING or self._turn_seat != seat:
            return []
        trick = self.state.round.current_trick()
        led = trick.led_suit if trick else None
        hand = self.state.player(seat).hand
        if led is None:
            return list(hand)  # leader can play any card
        # Must follow the led suit if possible.
        following = [c for c in hand if c.suit == led]
        return following if following else list(hand)

    def private_hand(self, seat: int) -> list[Card]:
        """Exposed ONLY to the authenticated player in their own view."""
        return list(self.state.player(seat).hand)

    # ------------------------------------------------------------- validation
    def validate_action(self, action: GameAction) -> None:
        """Raise if `action` is illegal. Never mutates state."""
        if action.type in (ActionType.SELECT_TRUMP, ActionType.PLAY_CARD) and action.seat not in range(NUM_PLAYERS):
            raise InvalidActionError(f"invalid seat {action.seat}")

        if action.type == ActionType.SELECT_TRUMP:
            self._validate_select_trump(action)
        elif action.type == ActionType.PLAY_CARD:
            self._validate_play_card(action)
        else:
            raise InvalidActionError(f"unknown action {action.type}")

    def _validate_select_trump(self, action: GameAction) -> None:
        if self.state.phase != GamePhase.TRUMP_SELECTION:
            raise InvalidActionError("game is not in trump selection")
        if action.seat != self.hakem_seat:
            raise InvalidActionError("only the hakem selects trump")
        if action.trump not in ALL_SUITS:
            raise InvalidActionError("invalid trump suit")
        if self.state.round.trump is not None:
            raise InvalidActionError("trump already selected")

    def _validate_play_card(self, action: GameAction) -> None:
        if self.state.phase != GamePhase.PLAYING:
            raise InvalidActionError("game is not in play phase")
        if self._turn_seat != action.seat:
            raise WrongTurnError(f"it is not seat {action.seat}'s turn")
        if action.card is None:
            raise InvalidActionError("play_card requires a card")
        hand = self.state.player(action.seat).hand
        if action.card not in hand:
            raise CardNotInHandError("you do not hold that card")
        trick = self.state.round.current_trick()
        led = trick.led_suit if trick else None
        if led is not None and action.card.suit != led:
            # Must follow suit if able to.
            has_led = any(c.suit == led for c in hand)
            if has_led:
                raise MustFollowSuitError("you must follow the led suit")
        if action.request_id in self._applied_request_ids:
            # Duplicate (e.g. a retried WebSocket command) -> no-op, treated as legal.
            return

    # ------------------------------------------------------------- transition
    def apply(self, action: GameAction) -> GameState:
        """Validate and apply `action`. Illegal actions raise WITHOUT mutating state.

        Idempotency: re-applying the same request_id is a no-op that returns the
        current (unchanged) state.
        """
        if action.request_id in self._applied_request_ids:
            # Already applied exactly once; do not execute twice.
            return self.state

        self.validate_action(action)  # raises before any mutation

        if action.type == ActionType.SELECT_TRUMP:
            self._apply_select_trump(action)
        elif action.type == ActionType.PLAY_CARD:
            self._apply_play_card(action)

        self._applied_request_ids.add(action.request_id)
        return self.state

    def _apply_select_trump(self, action: GameAction) -> None:
        state = self.state
        state.round.trump = action.trump
        state.phase = GamePhase.PLAYING
        leader = next_seat(self.hakem_seat)
        self._start_trick(leader)

    def _start_trick(self, leader: int) -> None:
        state = self.state
        trick = TrickState(leader_seat=leader)
        state.round.tricks.append(trick)
        state.round.leader_seat = leader
        self._turn_seat = leader

    def _apply_play_card(self, action: GameAction) -> None:
        state = self.state
        trick = state.round.current_trick()
        assert trick is not None and action.card is not None

        # Remove the card from the player's hand.
        hand = state.player(action.seat).hand
        hand.remove(action.card)
        state.player(action.seat).played_cards.append(action.card)
        trick.plays.append((action.seat, action.card))

        if not trick.complete:
            self._turn_seat = next_seat(action.seat)
            return

        # Trick complete -> resolve winner.
        winner_seat, winning_card = self.determine_trick_winner(trick)
        trick.winner_seat = winner_seat
        trick.winning_card = winning_card
        winner_team = Team.seat_to_team(winner_seat)
        state.round.won_tricks[winner_team] += 1

        if len(state.round.tricks) == TRICKS_PER_ROUND:
            self._finish_game()
        else:
            self._start_trick(winner_seat)

    def determine_trick_winner(self, trick: TrickState) -> tuple[int, Card]:
        """Return (winner_seat, winning_card) for a complete trick."""
        if len(trick.plays) < NUM_PLAYERS:
            raise InvalidActionError("trick is not complete")
        led = trick.led_suit
        trump = self.state.round.trump
        if led is None or trump is None:
            raise InvalidActionError("cannot resolve winner before trump/led suit")
        best_seat, best_card = trick.plays[0]
        for seat, card in trick.plays[1:]:
            if beats(card, best_card, led, trump):
                best_seat, best_card = seat, card
        return best_seat, best_card

    def _finish_game(self) -> None:
        state = self.state
        state.phase = GamePhase.GAME_ENDED
        a = state.round.won_tricks[Team.A]
        b = state.round.won_tricks[Team.B]
        state.round.winner_team = Team.A if a > b else Team.B
        self._turn_seat = None

    # ----------------------------------------------------------------- result
    def result(self) -> dict:
        """Authoritative game result (server-only)."""
        state = self.state
        if state.phase != GamePhase.GAME_ENDED:
            raise InvalidActionError("game has not ended")
        a = state.round.won_tricks[Team.A]
        b = state.round.won_tricks[Team.B]
        winner = state.round.winner_team
        assert winner is not None
        return {
            "winner_team": winner.name,
            "scores": {"A": a, "B": b},
            "hakem_seat": state.round.hakem_seat,
            "trump": state.round.trump.value if state.round.trump else None,
            "rules_version": state.rules_version,
        }

    # ------------------------------------------------------------- projection
    def view_for(self, seat: int) -> dict:
        """Build a player-specific, safe projection.

        NEVER includes opponent hands, hidden server state, or the internal RNG.
        Private-information tests rely on this contract, so keep it restrictive.
        """
        state = self.state
        trick = state.round.current_trick()
        return {
            "rules_version": state.rules_version,
            "phase": state.phase.value,
            "seat": seat,
            "team": Team.seat_to_team(seat).name,
            "hakem_seat": state.round.hakem_seat,
            "trump": state.round.trump.value if state.round.trump else None,
            "current_player": self._turn_seat,
            "is_my_turn": self._turn_seat == seat,
            "hand": [c.id for c in self.private_hand(seat)],
            "legal_cards": [c.id for c in self.legal_cards(seat)],
            "trick": {
                "leader_seat": trick.leader_seat if trick else None,
                "plays": [(s, c.id) for s, c in (trick.plays if trick else [])],
                "complete": trick.complete if trick else False,
            },
            # Public per-seat played-card counts (front-end wants to render the table).
            "table": [
                {
                    "seat": s,
                    "team": Team.seat_to_team(s).name,
                    "played": [c.id for c in state.player(s).played_cards],
                    "cards_in_hand": len(state.player(s).hand),
                }
                for s in range(NUM_PLAYERS)
            ],
            "scores": {"A": state.round.won_tricks[Team.A], "B": state.round.won_tricks[Team.B]},
            "won_tricks": {"A": state.round.won_tricks[Team.A], "B": state.round.won_tricks[Team.B]},
            "tricks_played": len(state.round.tricks),
            "winner_team": state.round.winner_team.name if state.round.winner_team else None,
        }

    def snapshot(self) -> dict:
        """Full authoritative state (persisted server-side only)."""
        state = self.state
        return {
            "phase": state.phase.value,
            "rules_version": state.rules_version,
            "hakem_seat": state.round.hakem_seat,
            "trump": state.round.trump.value if state.round.trump else None,
            "turn_seat": self._turn_seat,
            "round": {
                "number": state.round.number,
                "won_tricks": {"A": state.round.won_tricks[Team.A], "B": state.round.won_tricks[Team.B]},
                "winner_team": state.round.winner_team.name if state.round.winner_team else None,
            },
            "hands": {str(s): [c.id for c in state.player(s).hand] for s in range(NUM_PLAYERS)},
            "tricks": [
                {
                    "leader_seat": t.leader_seat,
                    "winner_seat": t.winner_seat,
                    "plays": [(s, c.id) for s, c in t.plays],
                }
                for t in state.round.tricks
            ],
        }

    @staticmethod
    def restore(snapshot: dict, rng_dp: Optional[object] = None) -> "HokmEngine":
        """Rehydrate an engine from a snapshot (used after a backend restart)."""
        engine = HokmEngine(seed=snapshot["seed"], rules_version=snapshot["rules_version"])
        engine.state.phase = GamePhase(snapshot["phase"])
        engine.state.round.hakem_seat = snapshot["hakem_seat"]
        engine.state.round.trump = Suit(snapshot["trump"]) if snapshot["trump"] else None
        engine._turn_seat = snapshot["turn_seat"]
        rs = snapshot["round"]
        engine.state.round.won_tricks = {Team.A: rs["won_tricks"]["A"], Team.B: rs["won_tricks"]["B"]}
        engine.state.round.winner_team = Team[rs["winner_team"]] if rs["winner_team"] else None
        for s in range(NUM_PLAYERS):
            engine.state.player(s).hand = [
                Card(suit_from_id(c), rank_from_id(c)) for c in snapshot["hands"][str(s)]
            ]
        for t in snapshot["tricks"]:
            tr = TrickState(
                leader_seat=t["leader_seat"],
                plays=[(s, Card(suit_from_id(c), rank_from_id(c))) for s, c in t["plays"]],
                winner_seat=t["winner_seat"],
            )
            if tr.winner_seat is not None:
                tr.winning_card = tr.plays[[s for s, _ in tr.plays].index(tr.winner_seat)][1]
            engine.state.round.tricks.append(tr)
        return engine


_SUIT_FROM_CHAR = {
    "s": Suit.SPADES,
    "h": Suit.HEARTS,
    "d": Suit.DIAMONDS,
    "c": Suit.CLUBS,
}
_RANK_FROM_STR = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}


def suit_from_id(card_id: str) -> Suit:
    return _SUIT_FROM_CHAR[card_id[0]]


def rank_from_id(card_id: str) -> "Rank":
    from .cards import Rank

    return Rank(_RANK_FROM_STR[card_id[1:]])
