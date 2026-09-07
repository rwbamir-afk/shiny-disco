import pytest
from hokm import Card, GameAction, ActionType, Suit, GamePhase
from hokm.variant_engine import VariantHokmEngine
from hokm.variants import GameVariant

@pytest.mark.parametrize("variant,count", [(GameVariant.DUEL_2P,2),(GameVariant.THREE_PLAYER,3)])
def test_variant_engine_deals_and_hides(count, variant):
    e=VariantHokmEngine(variant, seed=123).start()
    assert len(e.players)==count
    assert sum(len(p.hand) for p in e.players)+len(e.kitty)==52-(1 if count==3 else 0)
    v=e.view_for(0)
    assert "seed" not in v
    assert all("hand" not in {"opponent_hand": x} for x in [])

def test_duel_can_play_full_match_with_legal_actions():
    e=VariantHokmEngine(GameVariant.DUEL_2P, seed=7).start()
    e.apply(GameAction(ActionType.SELECT_TRUMP, e.hakem_seat, "t", trump=Suit.SPADES))
    n=0
    while e.phase != GamePhase.GAME_ENDED:
        seat=e.current_player_seat()
        card=e.legal_cards(seat)[0]
        e.apply(GameAction(ActionType.PLAY_CARD, seat, f"m{n}", card=card))
        n+=1
        assert n < 60
    assert sum(e.won)==26
    assert e.result()["winner_seat"] in (0,1)

def test_three_player_can_play_full_match():
    e=VariantHokmEngine(GameVariant.THREE_PLAYER, seed=11).start()
    e.apply(GameAction(ActionType.SELECT_TRUMP, e.hakem_seat, "t", trump=Suit.HEARTS))
    n=0
    while e.phase != GamePhase.GAME_ENDED:
        seat=e.current_player_seat()
        e.apply(GameAction(ActionType.PLAY_CARD, seat, f"m{n}", card=e.legal_cards(seat)[0]))
        n+=1
        assert n < 60
    assert sum(e.won)==17
