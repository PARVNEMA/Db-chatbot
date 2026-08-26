"""Async database engine, session factory, and dependency.

Provides:
- Lazy engine creation with connection pooling
- ``get_db()`` FastAPI dependency that yields an ``AsyncSession``
- Connection retry with exponential backoff
- ``check_db_connection()`` for health-check endpoints
- ``dispose_engine()`` for graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Return the global async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            echo=settings.DB_ECHO,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an ``AsyncSession``.

    The session is committed automatically if no exception occurs.
    On error the transaction is rolled back and the exception is re-raised.
    The session is always closed at the end.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    """Ping the database and return ``True`` on success.

    Used by health-check endpoints.
    """
    try:
        engine = _get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health-check failed: %s", exc)
        return False


async def connect_with_retry(max_retries: int = 3, base_delay: float = 1.0) -> None:
    """Verify database connectivity with exponential backoff.

    Called during application startup to fail fast if the database
    is unreachable.

    Args:
        max_retries: Number of retry attempts.
        base_delay: Initial delay in seconds (doubled each retry).
    """
    for attempt in range(1, max_retries + 1):
        try:
            engine = _get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established (attempt %d)", attempt)
            return
        except Exception as exc:
            if attempt == max_retries:
                logger.error(
                    "Failed to connect to database after %d attempts: %s",
                    max_retries,
                    exc,
                )
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Database connection attempt %d/%d failed, retrying in %.1fs: %s",
                attempt,
                max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)


async def dispose_engine() -> None:
    """Dispose the global engine, closing all pooled connections.

    Should be called during application shutdown.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")