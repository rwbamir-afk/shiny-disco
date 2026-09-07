"""Information-safe expert Hokm bot.

The bot never reads opponent hands. It reconstructs only public information and
samples plausible hidden-card distributions before short deterministic rollouts.
This is a strength upgrade over the heuristic hard bot, not a source of hidden
information.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter

from hokm import Card, HokmEngine, Suit, beats, build_deck
from hokm.models import GamePhase, Team, TrickState

from .base import BotStrategy
from .difficulties import MediumBot, _best_in_trick, _public_trick, _winning_cards


def _stable_seed(*parts: object) -> int:
    raw = "|".join(map(str, parts)).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _public_cards(engine: HokmEngine) -> list[Card]:
    cards: list[Card] = []
    for p in engine.state.players:
        cards.extend(p.played_cards)
    trick = engine.state.round.current_trick()
    if trick:
        # Current trick cards are also present in played_cards, so do not add twice.
        pass
    return cards


def _clone_public_state(engine: HokmEngine, seat: int, rng: random.Random) -> HokmEngine:
    """Create a simulation from public state + the bot's own hand only."""
    sim = HokmEngine(seed=_stable_seed(engine.state.seed, seat, rng.random()), rules_version=engine.state.rules_version)
    sim.state.phase = engine.state.phase
    sim.state.round.number = engine.state.round.number
    sim.state.round.hakem_seat = engine.state.round.hakem_seat
    sim.state.round.trump = engine.state.round.trump
    sim._turn_seat = engine.current_player_seat()

    own = set(engine.private_hand(seat))
    seen = set(own)
    for card in _public_cards(engine):
        seen.add(card)

    unknown = [c for c in build_deck() if c not in seen]
    rng.shuffle(unknown)
    counts = {s: len(engine.state.player(s).hand) for s in range(4)}
    counts[seat] = len(own)
    cursor = 0

    for s in range(4):
        sim.state.player(s).played_cards = list(engine.state.player(s).played_cards)
        if s == seat:
            sim.state.player(s).hand = sorted(own)
        else:
            n = counts[s]
            sim.state.player(s).hand = sorted(unknown[cursor:cursor + n])
            cursor += n

    sim.state.round.tricks = []
    for t in engine.state.round.tricks:
        copied = TrickState(
            leader_seat=t.leader_seat,
            plays=list(t.plays),
            winner_seat=t.winner_seat,
            winning_card=t.winning_card,
        )
        sim.state.round.tricks.append(copied)
    sim.state.round.won_tricks = dict(engine.state.round.won_tricks)
    sim.state.round.winner_team = engine.state.round.winner_team
    return sim


def _rollout(sim: HokmEngine, policy: MediumBot, perspective: Team, max_steps: int = 80) -> float:
    """Finish a sampled state using legal heuristic play and score the result."""
    steps = 0
    while sim.phase != GamePhase.GAME_ENDED and steps < max_steps:
        seat = sim.current_player_seat()
        if seat is None:
            break
        legal = sim.legal_cards(seat)
        if not legal:
            break
        card = policy.choose_move(sim, seat)
        from hokm import GameAction, ActionType
        sim.apply(GameAction(ActionType.PLAY_CARD, seat, f"rollout-{steps}", card=card))
        steps += 1
    if sim.phase != GamePhase.GAME_ENDED:
        return 0.0
    result = sim.result()
    winner = Team[result["winner_team"]]
    return 1.0 if winner is perspective else -1.0


class ExpertBot(BotStrategy):
    """Sampling-based bot using only legal actions and public information."""

    difficulty = "expert"
    simulations_per_card = 6

    def choose_trump(self, engine: HokmEngine, seat: int) -> Suit:
        hand = engine.private_hand(seat)
        scores: Counter[Suit] = Counter()
        for c in hand:
            scores[c.suit] += 3 if c.rank.value >= 12 else 1
        # Prefer length, then high cards, with stable suit tie-break.
        return max(Suit, key=lambda s: (scores[s], -s.value.__hash__()))

    def choose_move(self, engine: HokmEngine, seat: int) -> Card:
        legal = engine.legal_cards(seat)
        if len(legal) <= 1:
            return legal[0]

        # Tactical fast path: never sacrifice a partner-winning trick when a cheap
        # legal card can be discarded.
        trick = _public_trick(engine)
        if trick and trick["plays"] and engine.trump:
            best_seat, _ = _best_in_trick(engine)
            if best_seat == Team.partner_seat(seat):
                led = [c for c in legal if c.suit == trick["led_suit"]]
                if led:
                    return min(led, key=lambda c: c.score_value)

        perspective = Team.seat_to_team(seat)
        seed = _stable_seed(engine.state.seed, seat, len(engine.state.round.tricks), engine.current_player_seat())
        rng = random.Random(seed)
        policy = MediumBot()
        scores: dict[Card, float] = {}
        for card in legal:
            total = 0.0
            for _ in range(self.simulations_per_card):
                sim = _clone_public_state(engine, seat, rng)
                from hokm import GameAction, ActionType
                sim.apply(GameAction(ActionType.PLAY_CARD, seat, f"expert-{card.id}-{_}", card=card))
                total += _rollout(sim, policy, perspective)
            # Small deterministic preference for preserving high cards when tied.
            scores[card] = total - card.score_value * 0.001
        return max(legal, key=lambda c: (scores[c], -c.score_value, c.id))
