"""Unit tests for dealing and hakem selection."""
from hokm import ActionType, Card, GameAction, HokmEngine, Suit


def test_each_player_receives_13_cards(engine):
    engine.start()
    assert engine.phase.value == "trump_selection"
    for s in range(4):
        assert len(engine.hand(s)) == 13


def test_dealing_does_not_create_cards(engine):
    engine.start()
    all_cards = [c for s in range(4) for c in engine.hand(s)]
    assert len(all_cards) == 52
    assert len(set(all_cards)) == 52  # no duplicates across hands


def test_hakem_is_a_valid_seat(engine):
    engine.start()
    assert 0 <= engine.hakem_seat <= 3


def test_deal_is_deterministic_for_same_seed():
    a = HokmEngine(seed=7)
    a.start()
    b = HokmEngine(seed=7)
    b.start()
    assert a.hakem_seat == b.hakem_seat
    assert [a.hand(s) for s in range(4)] == [b.hand(s) for s in range(4)]


def test_deal_differs_for_different_seeds():
    a = HokmEngine(seed=1)
    a.start()
    b = HokmEngine(seed=2)
    b.start()
    assert [a.hand(s) for s in range(4)] != [b.hand(s) for s in range(4)]


def test_first_leader_is_next_after_hakem(engine):
    engine.start()
    trump = engine.hand(engine.hakem_seat)[0].suit
    engine.apply(
        GameAction(type=ActionType.SELECT_TRUMP, seat=engine.hakem_seat, request_id="r0", trump=trump)
    )
    from hokm import next_seat

    assert engine.current_player_seat() == next_seat(engine.hakem_seat)
