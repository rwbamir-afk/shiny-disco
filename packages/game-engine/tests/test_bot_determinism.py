from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
sys.path.insert(0, str(ROOT / "packages" / "game-engine"))

from hokm import ActionType, GameAction, HokmEngine
from backend.bots.difficulties import EasyBot, get_bot


def _setup():
    e = HokmEngine(seed=1234)
    e.start()
    e.apply(GameAction(ActionType.SELECT_TRUMP, e.hakem_seat, "t", trump=e.hand(e.hakem_seat)[0].suit))
    return e


def test_easy_bot_is_stable_across_process_hash_seeds():
    a = _setup()
    b = _setup()
    bot = EasyBot()
    assert bot.choose_move(a, a.current_player_seat()).id == bot.choose_move(b, b.current_player_seat()).id


def test_expert_bot_only_returns_legal_card():
    e = _setup()
    seat = e.current_player_seat()
    bot = get_bot("expert")
    card = bot.choose_move(e, seat)
    assert card in e.legal_cards(seat)


def test_expert_bot_does_not_change_authoritative_state():
    e = _setup()
    seat = e.current_player_seat()
    before = e.view_for(seat)
    get_bot("expert").choose_move(e, seat)
    assert e.view_for(seat) == before
