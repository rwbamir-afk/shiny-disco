"""Pytest shared fixtures for the Hokm engine tests."""
import sys
from pathlib import Path

import pytest

# Make `hokm` importable regardless of where pytest is invoked from.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hokm import ActionType, GameAction, HokmEngine, Team
from hokm.cards import ALL_SUITS, Rank, Suit


def legal_first_card(eng: HokmEngine) -> "Card":
    """Deterministically pick a legal card for the current player."""
    seat = eng.current_player_seat()
    return eng.legal_cards(seat)[0]


def play_full_game(eng: HokmEngine, trump: Suit | None = None) -> HokmEngine:
    """Play a complete, legal game using the first legal card every turn."""
    eng.start()
    eng.apply(
        GameAction(
            type=ActionType.SELECT_TRUMP,
            seat=eng.hakem_seat,
            request_id="r_select",
            trump=trump or eng.hand(eng.hakem_seat)[0].suit,
        )
    )
    i = 1
    while eng.phase.value != "game_ended":
        seat = eng.current_player_seat()
        card = eng.legal_cards(seat)[0]
        eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=seat, request_id=f"r{i}", card=card))
        i += 1
    return eng


@pytest.fixture
def engine() -> HokmEngine:
    return HokmEngine(seed=1234)


@pytest.fixture
def trump() -> Suit:
    return Suit.HEARTS
