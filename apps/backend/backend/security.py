"""Security primitives: Telegram Mini App init-data verification and session tokens.

Never trust client-supplied identity. All identity flows through here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import jwt

from .config import get_settings

settings = get_settings()


# ---------------------------------------------------------------- init-data
def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram WebApp initData and return the authenticated user dict.

    Raises ValueError if the signature is invalid or the data is too old.
    """
    if not init_data:
        raise ValueError("missing initData")

    # Parse into a dict, keeping values intact (hash is removed for signing).
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("missing hash in initData")

    # Build data_check_string: keys sorted, joined as key=value with newline.
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # Secret key = HMAC of the bot token with key "WebAppData".
    secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise ValueError("invalid initData signature")

    # Enforce freshness.
    auth_date = data.get("auth_date")
    if auth_date:
        try:
            ts = int(auth_date)
        except ValueError:
            raise ValueError("invalid auth_date")
        if time.time() - ts > settings.telegram_max_age_seconds:
            raise ValueError("initData expired")

    # "id" must be present and numeric. Real Telegram nests user fields inside
    # a JSON-encoded "user" parameter rather than sending them top-level.
    if "user" in data:
        try:
            user_obj = json.loads(data["user"])
        except (json.JSONDecodeError, TypeError):
            raise ValueError("invalid user field in initData")
        for key in ("id", "first_name", "last_name", "username", "language_code", "photo_url"):
            if key in user_obj and key not in data:
                data[key] = user_obj[key]

    if "id" not in data:
        raise ValueError("initData missing user id")
    return data


# ---------------------------------------------------------------- access token
def create_access_token(user_id: str) -> str:
    """Short-lived signed access token (JWT)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Return the user_id from a valid access token. Raises jwt exceptions otherwise."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload["sub"]


# ---------------------------------------------------------------- refresh token
def generate_refresh_token() -> tuple[str, str]:
    """Return (opaque_refresh_token, sha256_hash_to_store)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_ttl_seconds)
