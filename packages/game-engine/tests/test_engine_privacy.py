"""Anti-leak / private-information tests (Section 72 of the spec).

These test the serialization boundary directly: a player's view must never
contain another player's unrevealed cards, regardless of what the front-end does.
"""
import pytest

from hokm import ActionType, GameAction, HokmEngine, Suit


def _visible_card_ids(view) -> set:
    ids = set(view["hand"])  # own hand
    for t in view["table"]:
        ids.update(t["played"])
    for s, c in view["trick"]["plays"]:
        ids.add(c)
    return ids


def _remaining_hand_ids(eng, seat) -> set:
    return {c.id for c in eng.hand(seat)}


def _assert_no_leak(eng, seat):
    view = eng.view_for(seat)
    visible = _visible_card_ids(view)
    own = _remaining_hand_ids(eng, seat)
    for other in range(4):
        if other == seat:
            continue
        other_remaining = _remaining_hand_ids(eng, other)
        leaked = visible & other_remaining
        assert not leaked, f"seat {seat} view leaks cards still held by seat {other}: {leaked}"
    # A player must always see exactly their own hand (not a subset of it).
    assert set(view["hand"]) == own


def _step_full_game_and_check(seed):
    eng = HokmEngine(seed=seed)
    eng.start()
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="t", trump=Suit.SPADES))
    for seat_all in range(4):
        _assert_no_leak(eng, seat_all)
    i = 1
    while eng.phase.value != "game_ended":
        seat = eng.current_player_seat()
        legal = eng.legal_cards(seat)
        if not legal:
            break
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=seat, request_id=f"r{i}", card=legal[0]))
        i += 1
        # Re-check the invariant after EVERY single action.
        for seat_all in range(4):
            _assert_no_leak(eng, seat_all)


@pytest.mark.parametrize("seed", [0, 11, 77])
def test_view_never_leaks_opponent_cards(seed):
    _step_full_game_and_check(seed)


def test_view_has_no_full_private_snapshot():
    eng = HokmEngine(seed=0)
    eng.start()
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="t", trump=Suit.SPADES))
    view = eng.view_for(0)
    # The view must NOT expose the server-only snapshot structure.
    assert "hands" not in view
    assert "snapshot" not in view
    assert "_rng" not in view
    # Public table never leaks *counts* beyond what was played.
    for t in view["table"]:
        assert t["cards_in_hand"] >= 0


def test_view_exposes_own_it_is_my_turn_correctly():
    eng = HokmEngine(seed=3)
    eng.start()
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="t", trump=Suit.SPADES))
    cur = eng.current_player_seat()
    assert eng.view_for(cur)["is_my_turn"] is True
    assert eng.view_for((cur + 1) % 4)["is_my_turn"] is False
