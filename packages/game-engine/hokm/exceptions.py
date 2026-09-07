"""Hokm engine — error hierarchy."""
from __future__ import annotations


class HokmError(Exception):
    """Base engine error. All engine failures derive from this."""


class InvalidActionError(HokmError):
    """The requested action is not legal in the current state (state unchanged)."""


class InvalidStateError(HokmError):
    """The engine was asked to transition from an impossible state."""


class CardNotInHandError(InvalidActionError):
    """The actor does not hold the card they tried to play."""


class WrongTurnError(InvalidActionError):
    """It is not this player's turn to act."""


class MustFollowSuitError(InvalidActionError):
    """The player must follow the led suit but tried to play another suit."""
