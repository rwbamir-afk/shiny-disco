"""Shared helpers for the engine test suite."""
from hokm import ActionType, GameAction, HokmEngine, Suit


def play_full_game(eng: HokmEngine, trump: Suit | None = None) -> HokmEngine:
    """Play a complete, legal game by always taking the first legal card."""
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
        if eng.legal_cards(seat):
            card = eng.legal_cards(seat)[0]
            eng.apply(GameAction(type=ActionType.PLAY_CARD, seat=seat, request_id=f"r{i}", card=card))
            i += 1
        else:
            break
    return eng
