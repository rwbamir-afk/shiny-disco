"""Playable non-classic trick-taking variants.

The product intentionally defines its own explicit rules for variants whose
regional rules differ between tables. The engine is deterministic and shares
Hokm's command/view contract so the backend can switch variants without
weakening server authority.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .actions import ActionType, GameAction
from .cards import ALL_SUITS, Card, Rank, Suit, build_deck
from .exceptions import CardNotInHandError, InvalidActionError, MustFollowSuitError, WrongTurnError
from .models import GamePhase
from .engine import beats
from .variants import GameVariant


@dataclass
class VariantPlayer:
    seat: int
    hand: list[Card] = field(default_factory=list)
    played: list[Card] = field(default_factory=list)


@dataclass
class VariantTrick:
    leader: int
    plays: list[tuple[int, Card]] = field(default_factory=list)
    winner: Optional[int] = None


class VariantHokmEngine:
    """Deterministic 2P/3P Hokm-family engine with the same safe API as HokmEngine.

    Duel: full 52-card deck, 13 cards each, remaining cards form a kitty. After
    every trick, the winner draws first and the other player draws second until
    the kitty is empty. Then play continues until both hands are empty.

    Three-player: one card (2C) is removed from the standard deck, leaving 51
    cards / 17 cards each. Each player is an independent team.
    """

    def __init__(self, variant: GameVariant, seed: int = 0, rules_version: str = "hokm-variant-v1") -> None:
        if variant not in (GameVariant.DUEL_2P, GameVariant.THREE_PLAYER):
            raise ValueError("VariantHokmEngine supports duel_2p and three_player only")
        self.variant = variant
        self.num_players = 2 if variant is GameVariant.DUEL_2P else 3
        self.cards_per_player = 13 if self.num_players == 2 else 17
        self.rules_version = rules_version
        self.seed = seed
        self._rng = random.Random(seed)
        self.players = [VariantPlayer(s) for s in range(self.num_players)]
        self.phase = GamePhase.IDLE
        self.hakem_seat = 0
        self.trump: Optional[Suit] = None
        self._turn: Optional[int] = None
        self.tricks: list[VariantTrick] = []
        self.won = [0] * self.num_players
        self.winner_seat: Optional[int] = None
        self.kitty: list[Card] = []
        self._requests: set[str] = set()

    @property
    def state(self):
        return self

    def current_player_seat(self) -> Optional[int]:
        return self._turn

    def start(self):
        deck = build_deck()
        if self.variant is GameVariant.THREE_PLAYER:
            deck.remove(Card(Suit.CLUBS, Rank.TWO))
        self._rng.shuffle(deck)
        self.hakem_seat = self._rng.randrange(self.num_players)
        for p in self.players:
            p.hand = []
            p.played = []
        for seat in range(self.num_players):
            start = seat * self.cards_per_player
            self.players[seat].hand = sorted(deck[start:start + self.cards_per_player])
        used = self.num_players * self.cards_per_player
        self.kitty = deck[used:]
        self.phase = GamePhase.TRUMP_SELECTION
        return self

    def hand(self, seat: int) -> list[Card]:
        return list(self.players[seat].hand)

    def private_hand(self, seat: int) -> list[Card]:
        return self.hand(seat)

    def legal_cards(self, seat: int) -> list[Card]:
        if self.phase != GamePhase.PLAYING or self._turn != seat:
            return []
        hand = self.players[seat].hand
        trick = self.tricks[-1] if self.tricks and self.tricks[-1].winner is None else None
        if not trick or not trick.plays:
            return list(hand)
        led = trick.plays[0][1].suit
        follow = [c for c in hand if c.suit == led]
        return follow or list(hand)

    def validate_action(self, action: GameAction):
        if action.request_id in self._requests:
            return
        if action.seat not in range(self.num_players):
            raise InvalidActionError("invalid seat")
        if action.type is ActionType.SELECT_TRUMP:
            if self.phase != GamePhase.TRUMP_SELECTION or action.seat != self.hakem_seat:
                raise InvalidActionError("only the hakem may select trump")
            if action.trump not in ALL_SUITS:
                raise InvalidActionError("invalid trump suit")
            return
        if action.type is not ActionType.PLAY_CARD or self.phase != GamePhase.PLAYING:
            raise InvalidActionError("game is not accepting this action")
        if action.seat != self._turn:
            raise WrongTurnError("wrong turn")
        if action.card is None or action.card not in self.players[action.seat].hand:
            raise CardNotInHandError("you do not hold that card")
        legal = self.legal_cards(action.seat)
        if action.card not in legal:
            raise MustFollowSuitError("you must follow the led suit")

    def apply(self, action: GameAction):
        if action.request_id in self._requests:
            return self
        self.validate_action(action)
        self._requests.add(action.request_id)
        if action.type is ActionType.SELECT_TRUMP:
            self.trump = action.trump
            self.phase = GamePhase.PLAYING
            self._start_trick((self.hakem_seat + 1) % self.num_players)
        else:
            self._play(action.seat, action.card)
        return self

    def _start_trick(self, leader: int):
        self.tricks.append(VariantTrick(leader=leader))
        self._turn = leader

    def _play(self, seat: int, card: Card):
        assert card is not None
        p = self.players[seat]
        p.hand.remove(card)
        p.played.append(card)
        trick = self.tricks[-1]
        trick.plays.append((seat, card))
        if len(trick.plays) < self.num_players:
            self._turn = (seat + 1) % self.num_players
            return
        best_seat, best_card = trick.plays[0]
        led = trick.plays[0][1].suit
        assert self.trump is not None
        for s, c in trick.plays[1:]:
            if beats(c, best_card, led, self.trump):
                best_seat, best_card = s, c
        trick.winner = best_seat
        self.won[best_seat] += 1
        if self.kitty:
            draw_order = [best_seat, (best_seat + 1) % self.num_players]
            for s in draw_order:
                if self.kitty:
                    self.players[s].hand.append(self.kitty.pop(0))
                    self.players[s].hand.sort()
        if all(not p.hand for p in self.players):
            self.phase = GamePhase.GAME_ENDED
            self.winner_seat = max(range(self.num_players), key=lambda s: self.won[s])
            self._turn = None
            return
        self._start_trick(best_seat)

    def result(self) -> dict:
        if self.phase != GamePhase.GAME_ENDED:
            raise InvalidActionError("game has not ended")
        return {
            "variant": self.variant.value,
            "winner_seat": self.winner_seat,
            "scores": {str(i): self.won[i] for i in range(self.num_players)},
            "hakem_seat": self.hakem_seat,
            "trump": self.trump.value if self.trump else None,
            "rules_version": self.rules_version,
        }

    def view_for(self, seat: int) -> dict:
        trick = self.tricks[-1] if self.tricks and self.tricks[-1].winner is None else None
        return {
            "variant": self.variant.value,
            "rules_version": self.rules_version,
            "phase": self.phase.value,
            "seat": seat,
            "team": str(seat),
            "hakem_seat": self.hakem_seat,
            "trump": self.trump.value if self.trump else None,
            "current_player": self._turn,
            "is_my_turn": self._turn == seat,
            "hand": [c.id for c in self.players[seat].hand],
            "legal_cards": [c.id for c in self.legal_cards(seat)],
            "trick": {"leader_seat": trick.leader if trick else None, "plays": [(s, c.id) for s, c in (trick.plays if trick else [])], "complete": bool(trick and len(trick.plays) == self.num_players)},
            "table": [{"seat": p.seat, "team": str(p.seat), "played": [c.id for c in p.played], "cards_in_hand": len(p.hand)} for p in self.players],
            "scores": {str(i): self.won[i] for i in range(self.num_players)},
            "won_tricks": {str(i): self.won[i] for i in range(self.num_players)},
            "tricks_played": len(self.tricks),
            "winner_team": str(self.winner_seat) if self.winner_seat is not None else None,
        }

    def snapshot(self) -> dict:
        return {
            "variant": self.variant.value,
            "phase": self.phase.value,
            "rules_version": self.rules_version,
            "seed": self.seed,
            "hakem_seat": self.hakem_seat,
            "trump": self.trump.value if self.trump else None,
            "turn_seat": self._turn,
            "scores": {str(i): self.won[i] for i in range(self.num_players)},
            "winner_seat": self.winner_seat,
            "hands": {str(i): [c.id for c in p.hand] for i, p in enumerate(self.players)},
            "kitty_count": len(self.kitty),
        }
