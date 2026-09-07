"""BotStrategy abstraction.

Bots use the SAME engine and the SAME legal-action rules as humans. They may
only inspect their own hand + public table information. They never access
opponents' hidden hands, so they can never cheat.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from hokm import Card, Suit


class BotStrategy(ABC):
    difficulty: str

    @abstractmethod
    def choose_trump(self, engine, seat: int) -> Suit:
        """Choose a trump suit (bot that is the hakem)."""

    @abstractmethod
    def choose_move(self, engine, seat: int) -> Card:
        """Choose a card to play. Must be one of engine.legal_cards(seat)."""
