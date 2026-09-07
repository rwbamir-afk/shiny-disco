import pytest

from hokm.variants import GameVariant, get_variant, require_playable, supported_variants


def test_variant_catalog_is_explicit():
    ids = {item["id"] for item in supported_variants()}
    assert {v.value for v in GameVariant} == ids


def test_playable_variant_catalog():
    assert require_playable(GameVariant.CLASSIC_4P).player_count == 4
    assert require_playable(GameVariant.DUEL_2P).player_count == 2
    assert require_playable(GameVariant.THREE_PLAYER).player_count == 3
    assert get_variant(GameVariant.SHELEM_4P).playable is False
    assert get_variant(GameVariant.NARES_4P).playable is False


@pytest.mark.parametrize("variant", [GameVariant.SHELEM_4P, GameVariant.NARES_4P])
def test_unfinished_variants_fail_closed(variant):
    with pytest.raises(ValueError, match="not playable yet"):
        require_playable(variant)


def test_unknown_variant_rejected():
    with pytest.raises(ValueError, match="unsupported game variant"):
        get_variant("unknown")
