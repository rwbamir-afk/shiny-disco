"""Bot difficulty implementations.

All bots are rule-legal; they only differ in decision quality (heuristics),
never in the legality of information they may see.
"""
from __future__ import annotations

from hokm import Card, Suit, beats
from hokm.models import Team

from .base import BotStrategy


def _public_trick(engine):
    trick = engine.state.round.current_trick()
    if trick is None:
        return None
    return {"led_suit": trick.led_suit, "plays": list(trick.plays), "complete": trick.complete}


def _winning_cards(legal, plays, led_suit, trump):
    """Cards in `legal` that would beat the current best card in `plays`."""
    if trump is None or not plays:
        return []
    best_seat, best_card = plays[0]
    for s, c in plays[1:]:
        if beats(c, best_card, led_suit, trump):
            best_card = c
    return [c for c in legal if beats(c, best_card, led_suit, trump)]


def _best_in_trick(engine):
    trick = engine.state.round.current_trick()
    if trick is None or not trick.plays:
        return None, None
    trump = engine.trump
    led = trick.led_suit
    best_seat, best_card = trick.plays[0]
    for s, c in trick.plays[1:]:
        if beats(c, best_card, led, trump):
            best_seat, best_card = s, c
    return best_seat, best_card


class EasyBot(BotStrategy):
    """Random but always legal."""

    difficulty = "easy"

    def choose_trump(self, engine, seat: int) -> Suit:
        suits: dict[Suit, int] = {}
        for c in engine.hand(seat):
            suits[c.suit] = suits.get(c.suit, 0) + 1
        return max(suits, key=suits.get)

    def choose_move(self, engine, seat: int) -> Card:
        legal = engine.legal_cards(seat)
        # Deterministic pick (stable per game+seat) so tests can reproduce bot games.
        import hashlib
        digest = hashlib.sha256(f"{engine.state.seed}:{seat}".encode()).digest()
        return legal[int.from_bytes(digest[:4], "big") % len(legal)]


class MediumBot(BotStrategy):
    """Follow suit, win tricks cheaply with trump, dump lowest off-suit."""

    difficulty = "medium"

    def choose_trump(self, engine, seat: int) -> Suit:
        suits: dict[Suit, int] = {}
        for c in engine.hand(seat):
            suits[c.suit] = suits.get(c.suit, 0) + 1
        return max(suits, key=suits.get)

    def choose_move(self, engine, seat: int) -> Card:
        legal = engine.legal_cards(seat)
        if len(legal) == 1:
            return legal[0]
        trick = _public_trick(engine)
        trump = engine.trump
        if trick is not None and trick["plays"] and trump is not None:
            led_suit = trick["led_suit"]
            winning = _winning_cards(legal, trick["plays"], led_suit, trump)
            if winning:
                # Win as cheaply as possible.
                return sorted(winning, key=lambda c: c.score_value)[0]
            # Cannot win. Prefer following the led suit with the lowest card.
            led = [c for c in legal if c.suit == led_suit]
            if led:
                return min(led, key=lambda c: c.score_value)
            return min(legal, key=lambda c: c.score_value)
        # Leading: lead the lowest non-trump card (safe), else lowest overall.
        if trump is not None:
            nontrump = [c for c in legal if c.suit != trump]
            if nontrump:
                return min(nontrump, key=lambda c: c.score_value)
        return min(legal, key=lambda c: c.score_value)


class HardBot(MediumBot):
    """Adds trump management: avoids wasting trump when the partner is winning."""

    difficulty = "hard"

    def choose_move(self, engine, seat: int) -> Card:
        legal = engine.legal_cards(seat)
        if len(legal) == 1:
            return legal[0]
        trick = _public_trick(engine)
        trump = engine.trump
        if trick is None or not trick["plays"] or trump is None:
            return super().choose_move(engine, seat)

        led_suit = trick["led_suit"]
        partner_seat = Team.partner_seat(seat)
        best_seat, _ = _best_in_trick(engine)
        partner_wins = best_seat == partner_seat
        winning = _winning_cards(legal, trick["plays"], led_suit, trump)

        if winning and not partner_wins:
            # Cash the trick cheaply.
            return sorted(winning, key=lambda c: c.score_value)[0]
        if winning and partner_wins:
            # Don't waste trump over a winning partner; play led-suit low.
            led = [c for c in legal if c.suit == led_suit]
            if led:
                return min(led, key=lambda c: c.score_value)
            return min(legal, key=lambda c: c.score_value)
        # Can't win the trick.
        led = [c for c in legal if c.suit == led_suit]
        if led:
            return min(led, key=lambda c: c.score_value)
        return min(legal, key=lambda c: c.score_value)


BOT_DIFFICULTIES = {
    "easy": EasyBot,
    "medium": MediumBot,
    "hard": HardBot,
}

# Imported lazily to avoid a circular import: ExpertBot builds on these helpers.
def _get_expert():
    from .expert import ExpertBot
    return ExpertBot



def get_bot(difficulty: str) -> BotStrategy:
    if difficulty == "expert":
        return _get_expert()()
    return BOT_DIFFICULTIES.get(difficulty, MediumBot)()
