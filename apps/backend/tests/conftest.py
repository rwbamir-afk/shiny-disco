"""Backend integration test conftest.

Sets up an isolated SQLite DB and the env BEFORE importing backend.* so the
module-level async engine binds to the test database. A single session-scoped
TestClient drives the whole app (one lifespan, one matchmaker task).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

# Isolated test DB (removed at session end).
TEST_DB = "/tmp/hokm_integration.db"

os.environ["HOKM_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ["HOKM_ENVIRONMENT"] = "test"
os.environ["HOKM_TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["HOKM_JWT_SECRET"] = "test-secret"
os.environ["HOKM_TURN_TIMEOUT_SECONDS"] = "30"
os.environ["HOKM_RECONNECT_GRACE_SECONDS"] = "60"

BACKEND_DIR = Path(__file__).resolve().parent.parent  # apps/backend
GAME_ENGINE_DIR = BACKEND_DIR.parent.parent / "packages" / "game-engine"  # packages/game-engine
for p in (str(BACKEND_DIR), str(GAME_ENGINE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def make_init_data(fields: dict, token: str = "test-token") -> str:
    """Build a valid Telegram WebApp initData string for the given fields."""
    fields = dict(fields)
    fields["auth_date"] = str(int(time.time()))
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def client_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    import backend.main as appmod

    with TestClient(appmod.app) as c:
        yield c


@pytest.fixture
def tg_auth():
    """Return the /auth/telegram flow producing a token dict for a fresh user."""

    def _auth(client_, telegram_id: int, username: str = None):
        fields = {"id": str(telegram_id), "first_name": "بازیکن"}
        if username:
            fields["username"] = username
        init_data = make_init_data(fields)
        resp = client_.post("/api/v1/auth/telegram", json={"init_data": init_data})
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _auth
