"""WebSocket connection manager.

Tracks live sockets per user and per game, and provides broadcast/send helpers.
Authorization is enforced at the endpoint layer (never trust a channel name).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._user_sockets: dict[str, WebSocket] = {}  # one active socket per user
        self._game_users: dict[str, set[str]] = {}
        self._game_spectators: dict[str, set[str]] = {}

    async def connect_user(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        # Replace any stale socket for the same user (reconnect semantics).
        self._user_sockets[user_id] = websocket

    async def disconnect_user(self, user_id: str, websocket: WebSocket) -> None:
        if self._user_sockets.get(user_id) is websocket:
            self._user_sockets.pop(user_id, None)

    def subscribe(self, game_id: str, user_id: str) -> None:
        self._game_users.setdefault(game_id, set()).add(user_id)

    def unsubscribe(self, game_id: str, user_id: str) -> None:
        self._game_users.get(game_id, set()).discard(user_id)
        self._game_spectators.get(game_id, set()).discard(user_id)

    def subscribe_spectator(self, game_id: str, user_id: str) -> None:
        self._game_spectators.setdefault(game_id, set()).add(user_id)

    def unsubscribe_spectator(self, game_id: str, user_id: str) -> None:
        self._game_spectators.get(game_id, set()).discard(user_id)

    async def broadcast_spectators(self, game_id: str, payload: dict[str, Any]) -> None:
        for user_id in list(self._game_spectators.get(game_id, set())):
            await self.send_to_user(user_id, payload)

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        ws = self._user_sockets.get(user_id)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            # Socket is dead; drop it. Reconnect will re-register.
            self._user_sockets.pop(user_id, None)

    async def broadcast(self, game_id: str, payload: dict[str, Any]) -> None:
        for user_id in list(self._game_users.get(game_id, set())):
            await self.send_to_user(user_id, payload)
