"""Quick-Match matchmaking service (Section 16/28/29).

Single-instance MVP: an in-memory queue with a background matcher. Rating range
expands over time and bots fill in after a configurable fallback delay.

The queue lock is held only to mutate the queue. Game creation happens OUTSIDE
the lock so status/dedup endpoints never block behind a slow create_game.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from sqlalchemy import select

from ..config import get_settings
from ..models import User, UserProfile

settings = get_settings()


@dataclass
class QueueEntry:
    user_id: str
    rating: int
    display_name: str
    username: str | None
    enqueued_at: float


class MatchmakingService:
    def __init__(self, game_service) -> None:
        self.game_service = game_service
        self._session_factory = game_service._session_factory
        self._queue: list[QueueEntry] = []
        self._lock = asyncio.Lock()
        self._session_state: dict[str, dict] = {}
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    # ------------------------------------------------------------------ API
    async def enqueue(self, user_id: str) -> dict:
        async with self._lock:
            if any(e.user_id == user_id for e in self._queue):
                return {"status": "searching"}
            async with self._session_factory() as db:
                profile = (
                    (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id)))
                    .scalar_one_or_none()
                )
                user = await db.get(User, user_id)
            rating = profile.rating if profile else 1000
            self._queue.append(
                QueueEntry(
                    user_id=user_id,
                    rating=rating,
                    display_name=(user.first_name if user else "بازیکن"),
                    username=user.username if user else None,
                    enqueued_at=time.time(),
                )
            )
            self._session_state[user_id] = {"status": "searching"}
        return {"status": "searching"}

    async def status(self, user_id: str) -> dict:
        async with self._lock:
            st = self._session_state.get(user_id, {})
            return {"status": st.get("status", "no_game"), "game_id": st.get("game_id")}

    async def dequeue(self, user_id: str) -> None:
        async with self._lock:
            self._queue = [e for e in self._queue if e.user_id != user_id]
            self._session_state.pop(user_id, None)

    # ------------------------------------------------------------------ matcher
    async def _run(self) -> None:
        while True:
            try:
                await self._match_once()
            except Exception:
                pass  # A bad match attempt must not kill the matcher.
            await asyncio.sleep(0.75)

    async def _pop_group(self) -> tuple[list[QueueEntry], bool]:
        """Under the lock: decide a group and remove it from the queue.

        Returns (group, with_bots). Never references the queue after returning.
        """
        now = time.time()
        async with self._lock:
            if not self._queue:
                return [], False
            if len(self._queue) >= 4:
                group = self._queue[:4]
                self._queue = self._queue[4:]
                return group, False
            oldest = self._queue[0]
            waited = now - oldest.enqueued_at
            if settings.mm_bot_fallback_enabled and waited >= settings.mm_bot_fallback_seconds:
                group = self._queue
                self._queue = []
                return group, True
            return [], False

    async def _match_once(self) -> None:
        group, with_bots = await self._pop_group()
        if not group:
            return
        try:
            if with_bots:
                await self._form_group_with_bots(group)
            else:
                await self._form_game(group)
        except Exception:
            # On failure, requeue the humans so they are not silently dropped.
            async with self._lock:
                for e in group:
                    if not e.user_id.startswith("bot_"):
                        self._queue.append(e)
                        self._session_state[e.user_id] = {"status": "searching"}
            raise

    async def _form_game(self, group: list[QueueEntry]) -> None:
        seats = [
            {
                "user_id": e.user_id, "is_bot": False, "rating": e.rating,
                "display_name": e.display_name, "username": e.username,
            }
            for e in group
        ]
        async with self._session_factory() as db:
            runtime = await self.game_service.create_game(seats, db=db, config={"source": "matchmaking"})
        await self._mark_matched(group, runtime.game_id)

    async def _form_group_with_bots(self, group: list[QueueEntry]) -> None:
        seats = [
            {
                "user_id": e.user_id, "is_bot": False, "rating": e.rating,
                "display_name": e.display_name, "username": e.username,
            }
            for e in group
        ]
        while len(seats) < 4:
            seats.append(
                {"user_id": f"bot_{len(seats)}", "is_bot": True, "bot_difficulty": "medium",
                 "display_name": f"ربات {len(seats)}", "username": None, "rating": 1000}
            )
        async with self._session_factory() as db:
            runtime = await self.game_service.create_game(seats, db=db, config={"source": "matchmaking", "bots": True})
        await self._mark_matched(group, runtime.game_id)

    async def _mark_matched(self, group: list[QueueEntry], game_id: str) -> None:
        async with self._lock:
            for e in group:
                self._session_state[e.user_id] = {"status": "matched", "game_id": game_id}
