"""FastAPI application wiring.

Wires config, DB, services (game, matchmaking), connection manager, routers,
and the WebSocket endpoint. Single modular monolith process (Section 21/65).
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .middleware import RequestContextMiddleware, SimpleRateLimitMiddleware

from .config import get_settings
from .db import SessionLocal, engine
from .models import Base, User  # noqa: F401  (ensure models register on Base.metadata)
from .realtime.manager import ConnectionManager
from .routers import admin, auth, games, matchmaking, rankings, reports, rooms, users, economy, progression, social, clubs, tournaments, premium
from .security import decode_access_token
from .services.game_service import GameService
from .services.matchmaking_service import MatchmakingService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev/test bootstrap. Production uses Alembic migrations instead.
    if settings.environment != "prod":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    conn_manager = ConnectionManager()
    game_service = GameService(SessionLocal, conn_manager)
    app.state.session_factory = SessionLocal
    matchmaking_service = MatchmakingService(game_service)

    app.state.conn = conn_manager
    app.state.game_service = game_service
    app.state.matchmaking = matchmaking_service

    # Seed server-owned catalogs in dev and after migrations in production-safe deployments.
    from .services.economy_service import ensure_shop_catalog
    from .services.progression_service import ensure_catalog
    async with SessionLocal() as catalog_db:
        await ensure_shop_catalog(catalog_db)
        await ensure_catalog(catalog_db)
        await catalog_db.commit()

    matchmaking_service.start()
    try:
        yield
    finally:
        matchmaking_service.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(SimpleRateLimitMiddleware, limit=180, window_seconds=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()] if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, users, rooms, matchmaking, games, rankings, reports, admin, economy, progression, social, clubs, tournaments, premium):
    app.include_router(r.router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"ok": True, "app": settings.app_name, "env": settings.environment}

@app.get("/ready")
async def ready():
    """Readiness probe verifies that the configured database is reachable."""
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"ok": True, "ready": True}
    except Exception:
        return {"ok": False, "ready": False}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    conn_manager: ConnectionManager = websocket.app.state.conn  # type: ignore
    game_service: GameService = websocket.app.state.game_service  # type: ignore

    token = websocket.query_params.get("token")
    user_id = ""
    if token:
        try:
            user_id = decode_access_token(token)
        except Exception:
            pass
    if not user_id:
        await websocket.close(code=4401)
        return

    await conn_manager.connect_user(user_id, websocket)

    # Reconnect: locate any active game and resubscribe + resend authoritative state.
    game_id = await game_service.on_reconnect(user_id)
    runtime = game_service.registry.get(game_id) if game_id else None
    if runtime is not None:
        seat = runtime.seat_for_user(user_id)
        if seat is not None:
            conn_manager.subscribe(game_id, user_id)
            await conn_manager.send_to_user(
                user_id, {"type": "game.state", "data": game_service.view_payload(runtime, seat)}
            )

    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                await conn_manager.send_to_user(user_id, {"type": "error", "code": "bad_json", "error": "invalid json"})
                continue

            mtype = msg.get("type")
            if mtype == "ping":
                await conn_manager.send_to_user(user_id, {"type": "pong", "ts": msg.get("ts")})
            elif mtype == "state" or mtype == "subscribe":
                gid = msg.get("game_id") or game_id
                rt = game_service.registry.get(gid) if gid else None
                if rt is not None:
                    seat = rt.seat_for_user(user_id)
                    if seat is not None:
                        conn_manager.subscribe(gid, user_id)
                        await conn_manager.send_to_user(
                            user_id, {"type": "game.state", "data": game_service.view_payload(rt, seat)}
                        )
            elif mtype == "spectate":
                gid = msg.get("game_id")
                rt = game_service.registry.get(gid) if gid else None
                if rt is None:
                    await conn_manager.send_to_user(user_id, {"type": "error", "code": "game_not_found", "error": "live game not found"})
                elif rt.seat_for_user(user_id) is not None:
                    await conn_manager.send_to_user(user_id, {"type": "game.state", "data": game_service.view_payload(rt, rt.seat_for_user(user_id))})
                else:
                    conn_manager.subscribe_spectator(gid, user_id)
                    await conn_manager.send_to_user(user_id, {"type": "game.spectator", "data": game_service.spectator_payload(rt)})
            elif mtype == "game.action":
                gid = msg.get("game_id") or game_id
                action = msg.get("action") or {}
                out = await game_service.handle_action(gid, user_id, action)
                if not out.get("ok"):
                    await conn_manager.send_to_user(
                        user_id, {"type": "error", "code": out.get("code", "bad_action"), "error": out.get("error", "")}
                    )
                else:
                    await conn_manager.send_to_user(user_id, {"type": "game.state", "data": out.get("view")})
            else:
                await conn_manager.send_to_user(user_id, {"type": "error", "code": "unknown_event", "error": f"unknown type {mtype}"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await conn_manager.disconnect_user(user_id, websocket)
        await game_service.on_disconnect(user_id)
