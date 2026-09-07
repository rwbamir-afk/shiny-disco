"""Async SQLAlchemy engine + session management (SQLite dev / PostgreSQL prod)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_settings = get_settings()

# Render/PostgreSQL commonly provides a standard postgresql:// URL.
# SQLAlchemy's async engine in this project uses asyncpg.
_database_url = _settings.database_url
if _database_url.startswith("postgresql://"):
    _database_url = _database_url.replace(
        "postgresql://",
        "postgresql+asyncpg://",
        1,
    )

engine: AsyncEngine = create_async_engine(
    _database_url,
    echo=_settings.echo_sql,
    pool_pre_ping=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a scoped async session with commit/rollback handling."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
