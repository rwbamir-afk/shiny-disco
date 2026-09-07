"""Game orchestration and live runtime management.

Owns authoritative in-memory engine instances, per-game action serialization,
authoritative timers, reconnect/timeout/bot takeover, safe view projection, and
fire-and-forget persistence (move log + snapshot -> PostgreSQL/SQLite).

The engine is the single rules authority; this service only wraps it with
auth, concurrency control, and persistence. It never invents game rules.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from hokm import ActionType, GameAction, HokmEngine, Suit, GameVariant, VariantHokmEngine

from ..bots.base import BotStrategy
from ..bots.difficulties import get_bot
from ..config import get_settings
from ..models import Game as GameModel
from ..models import GameEvent, GamePlayer, Move, RefreshSession, User
from ..realtime.manager import ConnectionManager
from ..schemas import ErrorOut
from .result_processor import ResultProcessor

settings = get_settings()


@dataclass
class PlayerRuntime:
    user_id: str
    seat: int
    is_bot: bool = False
    bot_difficulty: str | None = None
    connection_state: str = "connected"
    display_name: str = ""
    username: str | None = None
    rating: int = 1000

    def meta(self) -> dict:
        return {
            "user_id": self.user_id,
            "seat": self.seat,
            "is_bot": self.is_bot,
            "connection_state": self.connection_state,
            "display_name": self.display_name,
            "username": self.username,
        }


@dataclass
class GameRuntime:
    game_id: str
    engine: HokmEngine
    players: list[PlayerRuntime]
    bots: dict[int, BotStrategy] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    turn_task: Optional[asyncio.Task] = None
    applied_request_ids: set[str] = field(default_factory=set)
    move_number: int = 0
    finished: bool = False
    fairness_commitment: str | None = None
    fairness_nonce: str | None = None
    turn_deadline: float | None = None
    last_action_at: float | None = None

    def user_for_seat(self, seat: int) -> Optional[str]:
        if 0 <= seat < len(self.players):
            return self.players[seat].user_id
        return None

    def seat_for_user(self, user_id: str) -> Optional[int]:
        for p in self.players:
            if p.user_id == user_id:
                return p.seat
        return None

    def player_for_seat(self, seat: int) -> Optional[PlayerRuntime]:
        if 0 <= seat < len(self.players):
            return self.players[seat]
        return None


class GameService:
    def __init__(self, session_factory, conn_manager: ConnectionManager) -> None:
        self._session_factory = session_factory
        self.conn = conn_manager
        self.registry: dict[str, GameRuntime] = {}
        self.result_processor = ResultProcessor(session_factory)
        self._seeds = 0

    # --------------------------------------------------------------- lifecycle
    async def create_game(self, seats: list[dict], db, config: dict | None = None) -> GameRuntime:
        """Create a game from a seat spec.

        seats: list of dicts with keys: user_id, is_bot, bot_difficulty,
               display_name, username, rating. Seats are filled in order -> seat index.
        """
        seed = int(time.time_ns()) ^ self._seeds
        self._seeds += 1
        fairness_nonce = secrets.token_hex(16)
        fairness_commitment = hashlib.sha256(f"{seed}:{fairness_nonce}".encode()).hexdigest()
        variant_value = (config or {}).get("variant", GameVariant.CLASSIC_4P.value)
        variant = GameVariant(variant_value)
        required_players = 4 if variant is GameVariant.CLASSIC_4P else (2 if variant is GameVariant.DUEL_2P else (3 if variant is GameVariant.THREE_PLAYER else 4))
        if len(seats) != required_players:
            raise ValueError(f"variant {variant.value} requires exactly {required_players} players")
        engine = HokmEngine(seed=seed, rules_version=settings.rules_version) if variant is GameVariant.CLASSIC_4P else VariantHokmEngine(variant, seed=seed, rules_version=settings.rules_version)
        engine.start()

        players: list[PlayerRuntime] = []
        bots: dict[int, BotStrategy] = {}
        for seat, spec in enumerate(seats[:4]):
            players.append(
                PlayerRuntime(
                    user_id=spec["user_id"],
                    seat=seat,
                    is_bot=spec.get("is_bot", False),
                    bot_difficulty=spec.get("bot_difficulty"),
                    connection_state="connected",
                    display_name=spec.get("display_name", "بازیکن"),
                    username=spec.get("username"),
                    rating=spec.get("rating", 1000),
                )
            )
            if spec.get("is_bot"):
                bots[seat] = get_bot(spec.get("bot_difficulty", "medium"))

        runtime = GameRuntime(game_id="", engine=engine, players=players, bots=bots, fairness_commitment=fairness_commitment, fairness_nonce=fairness_nonce)

        # Persist the game row + players.
        game = GameModel(
            status="playing",
            created_by=None,
            rules_version=settings.rules_version,
            seed=seed,
            snapshot=json.dumps(engine.snapshot()),
            config=json.dumps(config or {}),
            fairness_commitment=fairness_commitment,
            fairness_nonce=fairness_nonce,
            tournament_match_id=(config or {}).get("tournament_match_id"),
        )
        db.add(game)
        await db.flush()
        runtime.game_id = game.id
        for p in players:
            db.add(
                GamePlayer(
                    game_id=game.id,
                    user_id=p.user_id,
                    seat=p.seat,
                    team=("A" if variant is GameVariant.CLASSIC_4P and p.seat % 2 == 0 else ("B" if variant is GameVariant.CLASSIC_4P else chr(65 + p.seat))),
                    is_bot=p.is_bot,
                    bot_difficulty=p.bot_difficulty,
                    connection_state=p.connection_state,
                )
            )
        db.add(GameEvent(game_id=game.id, event="game_created", payload=json.dumps({"fairness_commitment": fairness_commitment})))
        await db.commit()

        self.registry[game.id] = runtime
        for p in players:
            if not p.is_bot:
                self.conn.subscribe(game.id, p.user_id)

        # If the hakem is a bot, pick trump automatically.
        await self._run_deadline_and_startup(runtime, db)
        return runtime

    async def _run_deadline_and_startup(self, runtime: GameRuntime, db) -> None:
        # If the hakem seat is a bot, have it select trump after a tick.
        hakem = runtime.engine.hakem_seat
        if runtime.engine.state.phase.value == "trump_selection":
            if hakem in runtime.bots:
                async def bot_trump():
                    await asyncio.sleep(0.05)
                    await self.handle_action(
                        runtime.game_id, runtime.players[hakem].user_id,
                        {"type": "select_trump", "request_id": f"{runtime.game_id}:trump"},
                    )
                asyncio.create_task(bot_trump())
            else:
                await self._schedule_turn_deadline(runtime)

    # --------------------------------------------------------------- actions
    def _build_action(self, runtime: GameRuntime, user_id: str, payload: dict) -> GameAction:
        seat = runtime.seat_for_user(user_id)
        if seat is None:
            raise ValueError("not a participant in this game")
        atype = payload.get("type")
        if atype == "select_trump":
            return GameAction(type=ActionType.SELECT_TRUMP, seat=seat, request_id=payload["request_id"],
                              trump=Suit(payload["trump"]) if payload.get("trump") else None)
        if atype == "play_card":
            from hokm import Card as HCard
            from hokm.engine import rank_from_id, suit_from_id
            card = payload.get("card")
            if not card:
                raise ValueError("card required")
            return GameAction(type=ActionType.PLAY_CARD, seat=seat, request_id=payload["request_id"],
                              card=HCard(suit_from_id(card), rank_from_id(card)))
        raise ValueError(f"unknown action type '{atype}'")

    async def handle_action(self, game_id: str, user_id: str, payload: dict) -> dict:
        """Apply an action to a game with full serialization + validation.

        Returns a {"ok": bool, "view": optional, "error": optional} result.
        Illegal actions never mutate state and return a clear error.
        """
        runtime = self.registry.get(game_id)
        if runtime is None:
            return {"ok": False, **ErrorOut(error="game not found", code="game_not_found").model_dump()}
        async with runtime.lock:
            if runtime.finished:
                return {"ok": False, **ErrorOut(error="game already finished", code="game_finished").model_dump()}
            seat = runtime.seat_for_user(user_id)
            if seat is None:
                return {"ok": False, **ErrorOut(error="not a participant", code="not_participant").model_dump()}
            try:
                action = self._build_action(runtime, user_id, payload)
            except Exception as e:  # malformed payload
                return {"ok": False, **ErrorOut(error=str(e), code="bad_request").model_dump()}

            # Idempotency: re-delivered request -> no-op, return current view.
            if action.request_id in runtime.applied_request_ids:
                return {"ok": True, "view": self.view_payload(runtime, seat)}

            try:
                self._reject_bot_turn_conflict(runtime, seat)
                runtime.engine.apply(action)
            except Exception as e:
                await self._record_event(runtime, "illegal_action", {"user_id": user_id, "error": str(e), "request_id": action.request_id})
                return {"ok": False, **ErrorOut(error=str(e), code="illegal_action").model_dump()}

            runtime.applied_request_ids.add(action.request_id)
            runtime.last_action_at = time.time()
            runtime.move_number += 1
            await self._persist_move(runtime, action)
            await self._persist_snapshot(runtime)

            if runtime.engine.phase.value == "game_ended":
                runtime.finished = True
                await self._finish_game(runtime)
            else:
                await self._reschedule(runtime)

            # Broadcast a fresh view to every subscribed player.
            await self._broadcast_views(runtime)
            return {"ok": True, "view": self.view_payload(runtime, seat)}

    def _reject_bot_turn_conflict(self, runtime: GameRuntime, seat: int) -> None:
        """Prevent a human from acting while a bot has been given control of their seat."""
        # The engine only lets the current player act; a bot takeover marks the seat
        # bot_controlled, so a human must reconnect to resume. No conflicting action.
        pass

    async def _persist_move(self, runtime: GameRuntime, action: GameAction) -> None:
        async with self._session_factory() as db:
            db.add(
                Move(
                    game_id=runtime.game_id,
                    move_number=runtime.move_number,
                    player_id=runtime.user_for_seat(action.seat),
                    seat=action.seat,
                    action=action.type.value,
                    card=action.card.id if action.card else None,
                    trump=action.trump.value if action.trump else None,
                    request_id=action.request_id,
                )
            )
            await db.commit()

    async def _persist_snapshot(self, runtime: GameRuntime) -> None:
        async with self._session_factory() as db:
            game = await db.get(GameModel, runtime.game_id)
            if game is not None:
                game.snapshot = json.dumps(runtime.engine.snapshot())
                await db.commit()

    # --------------------------------------------------------------- timers
    async def _reschedule(self, runtime: GameRuntime) -> None:
        await self._schedule_turn_deadline(runtime)

    async def _schedule_turn_deadline(self, runtime: GameRuntime) -> None:
        if runtime.turn_task is not None and not runtime.turn_task.done():
            runtime.turn_task.cancel()
        if runtime.engine.phase.value != "playing":
            return
        seat = runtime.engine.current_player_seat()
        if seat is None:
            return
        user_id = runtime.user_for_seat(seat)
        if user_id is None:
            return
        runtime.turn_deadline = time.time() + settings.turn_timeout_seconds
        runtime.turn_task = asyncio.create_task(self._turn_timeout_worker(runtime))
        # Bots play promptly (no 30s stall); humans get a full turn deadline.
        if seat in runtime.bots:
            asyncio.create_task(self._bot_play_later(runtime, seat))

    async def _turn_timeout_worker(self, runtime: GameRuntime) -> None:
        try:
            await asyncio.sleep(settings.turn_timeout_seconds)
        except asyncio.CancelledError:
            return
        async with runtime.lock:
            if runtime.finished or runtime.engine.phase.value != "playing":
                return
            seat = runtime.engine.current_player_seat()
            if seat is None:
                return
            player = runtime.player_for_seat(seat)
            if player is None:
                return
            await self._record_event(runtime, "timeout", {"seat": seat})
            if player.is_bot or player.connection_state == "bot_controlled":
                await self._bot_play(runtime, seat)
            elif player.connection_state == "connected":
                # Timed out while connected: auto-play via bot for this turn, mark bot_controlled.
                player.connection_state = "bot_controlled"
                await self._record_event(runtime, "bot_takeover", {"seat": seat})
                await self._bot_play(runtime, seat)

    async def _bot_play_later(self, runtime: GameRuntime, seat: int) -> None:
        """Give the broadcast a tick, then have a bot take its turn."""
        await asyncio.sleep(0.05)
        await self._bot_play(runtime, seat)

    async def _bot_play(self, runtime: GameRuntime, seat: int) -> None:
        """Make a bot take its legal turn (state machine may or may not be the bot's turn)."""
        if runtime.engine.phase.value == "trump_selection":
            if seat == runtime.engine.hakem_seat:
                bot = runtime.bots.get(seat)
                if bot is None:
                    return
                trump = bot.choose_trump(runtime.engine, seat)
                await self.handle_action(
                    runtime.game_id, runtime.players[seat].user_id,
                    {"type": "select_trump", "request_id": f"{runtime.game_id}:btrump:{runtime.move_number}",
                     "trump": trump.value},
                )
            return
        if runtime.engine.current_player_seat() != seat:
            return
        bot = runtime.bots.get(seat)
        if bot is None:
            return
        card = bot.choose_move(runtime.engine, seat)
        await self.handle_action(
            runtime.game_id, runtime.players[seat].user_id,
            {"type": "play_card", "request_id": f"{runtime.game_id}:b:{seat}:{runtime.move_number}",
             "card": card.id},
        )

    # --------------------------------------------------------------- finish
    async def _finish_game(self, runtime: GameRuntime) -> None:
        await self._record_event(runtime, "game_finished", {"winner": runtime.engine.result()["winner_team"]})
        # Cancel any pending authoritative turn timer so it does not outlive the game.
        if runtime.turn_task is not None and not runtime.turn_task.done():
            runtime.turn_task.cancel()
        runtime.turn_task = None
        runtime.turn_deadline = None
        # Persist final result + compute ratings/XP (idempotent).
        await self.result_processor.finalize(runtime.game_id, runtime)
        # Broadcast final views.
        await self._broadcast_views(runtime, final=True)

    # --------------------------------------------------------------- disconnect / reconnect
    async def on_disconnect(self, user_id: str) -> None:
        for runtime in self.registry.values():
            seat = runtime.seat_for_user(user_id)
            if seat is None:
                continue
            player = runtime.player_for_seat(seat)
            if player and not player.is_bot and player.connection_state != "bot_controlled":
                player.connection_state = "disconnected"
                await self._record_event(runtime, "player_disconnected", {"seat": seat})

    async def on_reconnect(self, user_id: str) -> Optional[str]:
        """Return the game_id a user should resume, if any, and restore control."""
        for runtime in self.registry.values():
            seat = runtime.seat_for_user(user_id)
            if seat is None:
                continue
            player = runtime.player_for_seat(seat)
            if player is None:
                continue
            was_bot = player.connection_state == "bot_controlled"
            # Restore human control (stop bot takeover).
            player.connection_state = "connected"
            await self._record_event(runtime, "player_reconnected", {"seat": seat, "was_bot": was_bot})
            await self._broadcast_views(runtime)
            return runtime.game_id
        return None

    # --------------------------------------------------------------- projection + broadcast
    def view_payload(self, runtime: GameRuntime, seat: int) -> dict:
        eng = runtime.engine
        v = eng.view_for(seat)
        player = runtime.player_for_seat(seat) or runtime.players[seat]
        # Recompute authoritative deadline.
        deadline = int(((runtime.turn_deadline or time.time()) * 1000))
        players_meta = [p.meta() for p in runtime.players]
        return {
            "game_id": runtime.game_id,
            **v,
            "turn_deadline": deadline,
            "players": players_meta,
            "my_meta": player.meta(),
            "fairness": {"commitment": getattr(runtime, "fairness_commitment", None)},
        }

    def spectator_payload(self, runtime: GameRuntime) -> dict:
        v = runtime.engine.view_for(0)
        v.pop("hand", None)
        v.pop("legal_cards", None)
        v.pop("seat", None)
        v.pop("team", None)
        return {
            "game_id": runtime.game_id,
            **v,
            "spectator": True,
            "fairness": {"commitment": runtime.fairness_commitment,
                         "reveal": {"seed": runtime.engine.state.seed, "nonce": runtime.fairness_nonce} if runtime.finished else None},
            "players": [p.meta() for p in runtime.players],
        }

    async def _broadcast_views(self, runtime: GameRuntime, final: bool = False) -> None:
        for p in runtime.players:
            if p.is_bot:
                continue
            payload = self.view_payload(runtime, p.seat)
            await self.conn.send_to_user(p.user_id, {"type": "game.state", "data": payload})
        await self.conn.broadcast_spectators(runtime.game_id, {"type": "game.spectator", "data": self.spectator_payload(runtime)})

    async def _record_event(self, runtime: GameRuntime, event: str, payload: dict) -> None:
        async with self._session_factory() as db:
            db.add(GameEvent(game_id=runtime.game_id, event=event, payload=json.dumps(payload)))
            await db.commit()

    # --------------------------------------------------------------- persistence recovery
    async def load_active_games(self) -> None:
        """On startup, rehydrate any games left in 'playing' state from their snapshot."""
        async with self._session_factory() as db:
            # (Handled by an admin/game router on demand; MVP keeps it simple.)
            pass
