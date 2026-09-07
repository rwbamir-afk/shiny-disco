"""Unit tests for the card/deck model."""
from hokm import ALL_SUITS, Card, Rank, Suit, build_deck


def test_deck_has_52_unique_cards():
    deck = build_deck()
    assert len(deck) == 52
    assert len(set(deck)) == 52


def test_each_suit_has_13_ranks():
    deck = build_deck()
    for suit in ALL_SUITS:
        ranks = {c.rank for c in deck if c.suit == suit}
        assert len(ranks) == 13
        assert set(ranks) == set(Rank)


def test_card_ids_are_unique():
    deck = build_deck()
    ids = [c.id for c in deck]
    assert len(ids) == len(set(ids))


def test_card_equality_and_hash():
    a = Card(Suit.HEARTS, Rank.ACE)
    b = Card(Suit.HEARTS, Rank.ACE)
    assert a == b
    assert hash(a) == hash(b)


def test_card_rank_order():
    assert Rank.TWO < Rank.TEN < Rank.JACK < Rank.QUEEN < Rank.KING < Rank.ACE
    assert int(Rank.ACE) == 14
    assert int(Rank.TEN) == 10


def test_card_sorting_is_deterministic():
    deck = build_deck()
    unsorted = deck[::-1]
    assert sorted(unsorted) == deck


def test_card_summary_no_duplicate_suit_values():
    assert len({s.value for s in ALL_SUITS}) == 4


def test_invalid_rank_rejected():
    import pytest

    with pytest.raises(TypeError):
        Card(Suit.SPADES, "A")  # string rank must be rejected
