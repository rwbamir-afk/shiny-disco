"""Rule-level tests: trump selection, follow-suit, trick/round winner, scoring,
illegal actions, and idempotency."""
import pytest

from hokm import (
    ActionType,
    Card,
    GameAction,
    HokmEngine,
    MustFollowSuitError,
    Suit,
    WrongTurnError,
)
from hokm.cards import Rank, build_deck
from hokm.engine import beats
from helpers import play_full_game

DECK = {c.id: c for c in build_deck()}


def make_engine_with_hands(hands, trump=Suit.HEARTS, hakem=0):
    eng = HokmEngine(seed=0)
    eng.start()
    eng.state.round.hakem_seat = hakem
    for s in range(4):
        eng.state.players[s].hand = list(hands[s])
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=hakem, request_id="t", trump=trump))
    return eng


# ------------------------------------------------------------------ trump
def test_trump_selection_by_hakem_only():
    eng = HokmEngine(seed=0)
    eng.start()
    hakem = eng.hakem_seat
    other = (hakem + 1) % 4
    with pytest.raises(Exception):
        eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=other, request_id="x", trump=Suit.SPADES))


def test_select_trump_sets_phase_and_trump(engine):
    engine.start()
    engine.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=engine.hakem_seat, request_id="r", trump=Suit.CLUBS))
    assert engine.trump == Suit.CLUBS
    assert engine.phase.value == "playing"


def test_trump_cannot_be_changed_after_selection(engine):
    engine.start()
    engine.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=engine.hakem_seat, request_id="r", trump=Suit.CLUBS))
    with pytest.raises(Exception):
        engine.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=engine.hakem_seat, request_id="r2", trump=Suit.SPADES))


def test_invalid_trump_suit_rejected(engine):
    engine.start()
    with pytest.raises(Exception):
        engine.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=engine.hakem_seat, request_id="r"))


# ------------------------------------------------------------------ hand control
def _suit_hand(suit, ranks):
    return [Card(suit, r if isinstance(r, Rank) else Rank(r)) for r in ranks]


def _controlled_hands_follow():
    # Leader (seat 1) leads H9; seat 2 holds H2 -> MUST follow hearts.
    return [
        _suit_hand(Suit.HEARTS, [3, 4, 5, 6, 7, 8, 10, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE])
        + [DECK["sA"], DECK["cA"]],
        _suit_hand(Suit.HEARTS, [9]) + _suit_hand(Suit.SPADES, [2, 3, 4, 5, 6, 7, 8, 9, 10, Rank.JACK, Rank.QUEEN, Rank.KING]),
        _suit_hand(Suit.HEARTS, [2]) + _suit_hand(Suit.CLUBS, [2, 3, 4, 5, 6, 7, 8, 9, 10, Rank.JACK, Rank.QUEEN, Rank.KING]),
        _suit_hand(Suit.DIAMONDS, list(Rank)),
    ]


def _controlled_hands_no_follow():
    # Leader (seat 1) leads H9; seat 2 holds NO hearts -> may play any card.
    return [
        _suit_hand(Suit.HEARTS, [2, 3, 4, 5, 6, 7, 8, 10, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE]) + [DECK["cA"]],
        _suit_hand(Suit.HEARTS, [9]) + _suit_hand(Suit.CLUBS, [2, 3, 4, 5, 6, 7, 8, 9, 10, Rank.JACK, Rank.QUEEN, Rank.KING]),
        _suit_hand(Suit.SPADES, list(Rank)),
        _suit_hand(Suit.DIAMONDS, list(Rank)),
    ]


def test_play_out_of_turn_rejected():
    hands = [
        _suit_hand(Suit.HEARTS, list(Rank)),
        _suit_hand(Suit.SPADES, list(Rank)),
        _suit_hand(Suit.DIAMONDS, list(Rank)),
        _suit_hand(Suit.CLUBS, list(Rank)),
    ]
    eng = make_engine_with_hands(hands)
    leader = eng.current_player_seat()
    non_leader = (leader + 1) % 4
    with pytest.raises(WrongTurnError):
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=non_leader, request_id="x", card=eng.hand(non_leader)[0]))


def test_play_card_not_in_hand_rejected():
    hands = [
        _suit_hand(Suit.HEARTS, list(Rank)),
        _suit_hand(Suit.SPADES, list(Rank)),
        _suit_hand(Suit.DIAMONDS, list(Rank)),
        _suit_hand(Suit.CLUBS, list(Rank)),
    ]
    eng = make_engine_with_hands(hands)
    leader = eng.current_player_seat()  # seat 1 (all spades) since hakem=0
    foreign = Card(Suit.HEARTS, Rank.ACE)  # seat 1 does NOT hold hearts
    with pytest.raises(Exception):
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=leader, request_id="x", card=foreign))


def test_follow_suit_enforced():
    eng = make_engine_with_hands(_controlled_hands_follow(), trump=Suit.SPADES, hakem=0)
    leader = eng.current_player_seat()
    assert leader == 1
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=leader, request_id="1", card=DECK["h9"]))
    nextp = eng.current_player_seat()
    assert nextp == 2
    # seat 2 holds a heart (H2) -> must follow; trying to play an off-suit club fails.
    with pytest.raises(MustFollowSuitError):
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=nextp, request_id="2", card=DECK["c2"]))
    # But playing the heart is legal.
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=nextp, request_id="2b", card=DECK["h2"]))
    assert eng.current_player_seat() == 3


def test_cannot_follow_suit_allows_any_card():
    eng = make_engine_with_hands(_controlled_hands_no_follow(), trump=Suit.SPADES, hakem=0)
    leader = eng.current_player_seat()
    assert leader == 1
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=leader, request_id="1", card=DECK["h9"]))
    nextp = eng.current_player_seat()
    assert nextp == 2
    # seat 2 holds no hearts -> may play any card (a spade here).
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=nextp, request_id="2", card=DECK["s2"]))
    assert eng.current_player_seat() == 3


# ------------------------------------------------------------------ trick winner
def test_trick_winner_trump_beats_non_trump():
    assert beats(Card(Suit.SPADES, Rank.TWO), Card(Suit.HEARTS, Rank.ACE), Suit.HEARTS, Suit.SPADES)
    assert not beats(Card(Suit.HEARTS, Rank.ACE), Card(Suit.SPADES, Rank.TWO), Suit.SPADES, Suit.SPADES)


def test_trick_winner_higher_trump():
    assert beats(Card(Suit.SPADES, Rank.KING), Card(Suit.SPADES, Rank.THREE), Suit.HEARTS, Suit.SPADES)


def test_trick_winner_higher_led_suit():
    assert beats(Card(Suit.HEARTS, Rank.KING), Card(Suit.HEARTS, Rank.FOUR), Suit.HEARTS, Suit.SPADES)
    assert not beats(Card(Suit.HEARTS, Rank.THREE), Card(Suit.HEARTS, Rank.KING), Suit.HEARTS, Suit.SPADES)


def test_trick_win_off_suit_cannot_beat_led():
    assert not beats(Card(Suit.DIAMONDS, Rank.ACE), Card(Suit.HEARTS, Rank.FOUR), Suit.HEARTS, Suit.SPADES)


# ------------------------------------------------------------------ full game
def test_full_game_completion_and_result():
    eng = play_full_game(HokmEngine(seed=99))
    assert eng.phase.value == "game_ended"
    res = eng.result()
    assert res["scores"]["A"] + res["scores"]["B"] == 13
    assert res["winner_team"] in ("A", "B")


def test_result_not_available_before_end(engine):
    engine.start()
    with pytest.raises(Exception):
        engine.result()


# ------------------------------------------------------------------ idempotency
def test_idempotent_apply():
    eng = HokmEngine(seed=5)
    eng.start()
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="r", trump=Suit.SPADES))
    before = eng.snapshot()
    eng.apply(GameAction(type=ActionType.SELECT_TRUMP, seat=eng.hakem_seat, request_id="r", trump=Suit.SPADES))
    assert eng.snapshot() == before


def test_played_card_removed_from_hand():
    eng = make_engine_with_hands(_controlled_hands_follow(), trump=Suit.SPADES, hakem=0)
    leader = eng.current_player_seat()
    card = DECK["h9"]
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=leader, request_id="1", card=card))
    assert card not in eng.hand(leader)


def test_trick_winner_persisted():
    eng = make_engine_with_hands(_controlled_hands_follow(), trump=Suit.SPADES, hakem=0)
    leader = eng.current_player_seat()
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=leader, request_id="1", card=DECK["h9"]))
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=2, request_id="2", card=DECK["h2"]))
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=3, request_id="3", card=eng.hand(3)[0]))
    eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=0, request_id="4", card=eng.hand(0)[0]))
    trick = eng.state.round.tricks[0]  # the first (completed) trick
    assert trick.complete
    assert trick.winner_seat is not None
