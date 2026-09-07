"""Backend runtime configuration (pydantic-settings).

Secrets come from environment variables. Never hardcode credentials.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOKM_", env_file=".env", extra="ignore")

    # App
    app_name: str = "Hokm Platform"
    environment: str = "dev"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: str = "*"

    # Database (async SQLAlchemy). SQLite for dev/test, PostgreSQL for prod.
    database_url: str = "sqlite+aiosqlite:///./hokm.db"
    echo_sql: bool = False

    # Redis (optional; falls back to in-memory when unavailable).
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False

    # Telegram Mini App init-data verification.
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_mini_app_short_name: str = ""
    telegram_max_age_seconds: int = 3600
    telegram_payment_webhook_secret: str = ""

    # Auth / sessions.
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30

    # Game rules.
    rules_version: str = "hokm-v1"

    # Timers / reliability (all server-authoritative).
    turn_timeout_seconds: int = 30
    reconnect_grace_seconds: int = 60
    bot_fallback_after_seconds: int = 60
    game_idle_cleanup_seconds: int = 3600

    # Matchmaking.
    mm_initial_rating_range: int = 100
    mm_max_rating_range: int = 800
    mm_range_expand_seconds: int = 15
    mm_bot_fallback_seconds: int = 45
    mm_bot_fallback_enabled: bool = True

    def _check_secrets(self) -> None:
        if self.environment == "prod" and self.jwt_secret == "change-me-in-prod":
            raise ValueError("JWT secret must be set in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings._check_secrets()
    return settings
