"""Explicit game-variant catalog and rule validation.

This module intentionally separates variant metadata from the classic Hokm
state machine. It prevents the backend from silently treating a 2/3-player
request as a 4-player game. Playable engines for non-classic variants can be
introduced behind the same contract later.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GameVariant(str, Enum):
    CLASSIC_4P = "classic_4p"
    DUEL_2P = "duel_2p"
    THREE_PLAYER = "three_player"
    SHELEM_4P = "shelem_4p"
    NARES_4P = "nares_4p"


@dataclass(frozen=True)
class VariantRules:
    variant: GameVariant
    display_name_fa: str
    player_count: int
    cards_per_player: int
    team_count: int
    playable: bool
    description_fa: str


VARIANTS: dict[GameVariant, VariantRules] = {
    GameVariant.CLASSIC_4P: VariantRules(
        GameVariant.CLASSIC_4P, "حکم کلاسیک", 4, 13, 2, True,
        "حکم استاندارد چهار نفره و تیمی.",
    ),
    GameVariant.DUEL_2P: VariantRules(
        GameVariant.DUEL_2P, "حکم دو نفره", 2, 13, 1, True,
        "نسخه دو نفره با کیتی؛ برنده هر تریک ابتدا کارت می‌کشد.",
    ),
    GameVariant.THREE_PLAYER: VariantRules(
        GameVariant.THREE_PLAYER, "حکم سه نفره", 3, 17, 3, True,
        "نسخه سه نفره مستقل؛ یک کارت حذف می‌شود و هر بازیکن تیم خودش است.",
    ),
    GameVariant.SHELEM_4P: VariantRules(
        GameVariant.SHELEM_4P, "شلم", 4, 13, 2, False,
        "شلم با مزایده و امتیازدهی مستقل از حکم کلاسیک.",
    ),
    GameVariant.NARES_4P: VariantRules(
        GameVariant.NARES_4P, "نارس", 4, 13, 2, False,
        "نارس؛ قرارداد مستقل تا زمان نهایی شدن قوانین محصول فعال نیست.",
    ),
}


def get_variant(value: str | GameVariant) -> VariantRules:
    try:
        return VARIANTS[GameVariant(value)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"unsupported game variant: {value}") from exc


def require_playable(value: str | GameVariant) -> VariantRules:
    rules = get_variant(value)
    if not rules.playable:
        raise ValueError(f"game variant is not playable yet: {rules.variant.value}")
    return rules


def supported_variants() -> list[dict]:
    return [
        {
            "id": r.variant.value,
            "name_fa": r.display_name_fa,
            "players": r.player_count,
            "cards_per_player": r.cards_per_player,
            "team_count": r.team_count,
            "playable": r.playable,
            "description_fa": r.description_fa,
        }
        for r in VARIANTS.values()
    ]
