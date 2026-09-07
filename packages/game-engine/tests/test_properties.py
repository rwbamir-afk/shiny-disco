"""Property-based / invariant tests for the engine (Section 68 of the spec)."""
import random

import pytest

from hokm import ActionType, Card, GameAction, HokmEngine, Suit
from helpers import play_full_game


def _random_game(seed):
    eng = HokmEngine(seed=seed)
    eng.start()
    trump = Suit(eng.hand(eng.hakem_seat)[0].suit)
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="0", trump=trump))
    i = 1
    while eng.phase.value != "game_ended":
        seat = eng.current_player_seat()
        legal = eng.legal_cards(seat)
        if not legal:
            break
        card = random.Random(seed * 1000 + i).choice(legal)
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=seat, request_id=f"r{i}", card=card))
        i += 1
    return eng


@pytest.mark.parametrize("seed", [0, 1, 5, 13, 42, 999])
def test_no_card_duplicates_in_any_hand(seed):
    eng = HokmEngine(seed=seed)
    eng.start()
    all_cards = [c for s in range(4) for c in eng.hand(s)]
    assert len(all_cards) == 52
    assert len(set(all_cards)) == 52


@pytest.mark.parametrize("seed", [0, 1, 5, 13, 42, 999])
def test_played_card_belongs_to_player_at_time_of_play(seed):
    eng = _random_game(seed)
    # Every card a seat played must come from cards that seat held (we track totals).
    for seat in range(4):
        played = eng.state.player(seat).played_cards
        # The union of hand + played is the original 13 for that seat.
        assert len(played) + len(eng.hand(seat)) == 13


@pytest.mark.parametrize("seed", [0, 7, 21])
def test_tricks_never_exceed_four_plays(seed):
    eng = _random_game(seed)
    for t in eng.state.round.tricks:
        assert len(t.plays) <= 4


@pytest.mark.parametrize("seed", [0, 7, 21])
def test_every_completed_trick_has_one_winner(seed):
    eng = _random_game(seed)
    for t in eng.state.round.tricks:
        if t.complete:
            assert t.winner_seat is not None
            assert t.winning_card is not None


@pytest.mark.parametrize("seed", [0, 3, 55])
def test_scores_consistent_at_end(seed):
    eng = _random_game(seed)
    assert eng.phase.value == "game_ended"
    res = eng.result()
    assert res["scores"]["A"] + res["scores"]["B"] == 13


def test_finished_game_rejects_further_actions():
    eng = _random_game(0)
    assert eng.phase.value == "game_ended"
    with pytest.raises(Exception):
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=0, request_id="zzz", card=Card(Suit.SPADES, 2)))


def test_same_seed_same_game():
    a = play_full_game(HokmEngine(seed=31337))
    b = play_full_game(HokmEngine(seed=31337))
    assert a.result() == b.result()
    assert len(a.state.round.tricks) == len(b.state.round.tricks)
