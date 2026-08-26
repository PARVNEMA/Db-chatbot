"""
Dynamic Multi-Tenant Connection Manager (ADR-0002).

Responsibilities:
- Decrypt Fernet-encrypted connection strings from the platform DB.
- Manage pooled SQLAlchemy async engines per (project_id, connection_id).
- Test connectivity and measure handshake latency.
- Enforce read-only guardrails, execution timeouts, and row limit caps.

This is the ONLY place in the codebase where connection strings are decrypted.
Raw credentials MUST NOT be logged or surfaced in API responses.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import decrypt

# Max rows returned per query execution
QUERY_ROW_LIMIT: int = 1000
# Query execution timeout in seconds
QUERY_TIMEOUT_SECONDS: int = 10

# DDL / DML keywords to block before execution
_BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {"insert", "update", "delete", "drop", "truncate", "alter", "create", "grant", "revoke"}
)


def mask_connection_string(conn_str: str) -> str:
    """Mask password credentials in a connection URL for safe logging/errors."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", conn_str)


def normalize_connection_url(conn_str: str) -> str:
    """Normalize database connection URLs to use SQLAlchemy async drivers.

    Transforms standard connection URL schemes:
    - postgresql://... -> postgresql+asyncpg://...
    - postgres://...   -> postgresql+asyncpg://...
    - sqlite://...     -> sqlite+aiosqlite://... (if not already prefixed with sqlite+)
    - mysql://...      -> mysql+asyncmy://... (if not already prefixed with mysql+)
    - mariadb://...    -> mariadb+asyncmy://... (if not already prefixed with mariadb+)
    """
    trimmed = conn_str.strip()
    if trimmed.startswith("postgresql://"):
        return "postgresql+asyncpg://" + trimmed[len("postgresql://") :]
    if trimmed.startswith("postgres://"):
        return "postgresql+asyncpg://" + trimmed[len("postgres://") :]
    if trimmed.startswith("sqlite://") and not trimmed.startswith("sqlite+"):
        return "sqlite+aiosqlite://" + trimmed[len("sqlite://") :]
    if trimmed.startswith("mysql://") and not trimmed.startswith("mysql+"):
        return "mysql+asyncmy://" + trimmed[len("mysql://") :]
    if trimmed.startswith("mariadb://") and not trimmed.startswith("mariadb+"):
        return "mariadb+asyncmy://" + trimmed[len("mariadb://") :]
    return trimmed


class ConnectionManager:
    """Manages pooled SQLAlchemy engines for tenant target databases."""

    def __init__(self) -> None:
        # Keyed by (project_id, connection_id) -> AsyncEngine
        self._engines: dict[tuple[uuid.UUID, uuid.UUID], AsyncEngine] = {}

    def _get_or_create_engine(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        encrypted_connection_string: str,
    ) -> AsyncEngine:
        key = (project_id, connection_id)
        if key not in self._engines:
            # Decrypt only here; never log the result
            plain_url = decrypt(encrypted_connection_string)
            normalized_url = normalize_connection_url(plain_url)
            self._engines[key] = create_async_engine(
                normalized_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._engines[key]

    def get_engine(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        encrypted_connection_string: str,
    ) -> AsyncEngine:
        """Return the pooled AsyncEngine for the tenant connection."""
        return self._get_or_create_engine(project_id, connection_id, encrypted_connection_string)

    def get_session(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        encrypted_connection_string: str,
    ) -> AsyncSession:
        """Return an AsyncSession bound to the tenant's target engine."""
        engine = self._get_or_create_engine(project_id, connection_id, encrypted_connection_string)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return session_factory()

    async def test_connection(
        self,
        connection_string: str,
        timeout_seconds: float = 5.0,
    ) -> tuple[bool, float | None, str | None, str]:
        """Test database connectivity with the provided connection string.

        Returns:
            (success, latency_ms, dialect, message)
        """
        temp_engine: AsyncEngine | None = None
        try:
            normalized_url = normalize_connection_url(connection_string)
            connect_args: dict[str, Any] = {}
            if "asyncpg" in normalized_url:
                connect_args = {"timeout": float(timeout_seconds)}

            temp_engine = create_async_engine(
                normalized_url,
                pool_pre_ping=True,
                connect_args=connect_args,
            )
            start_time = time.perf_counter()

            async def _ping() -> None:
                assert temp_engine is not None
                async with temp_engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            await asyncio.wait_for(_ping(), timeout=timeout_seconds)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            dialect_name = temp_engine.dialect.name
            return True, latency_ms, dialect_name, "Connection successful"
        except TimeoutError:
            return False, None, None, f"Connection timed out after {timeout_seconds}s"
        except Exception as exc:
            err_msg = str(exc)
            # Mask potential password leaks in error messages
            masked_msg = mask_connection_string(err_msg)
            return False, None, None, f"Connection failed: {masked_msg}"
        finally:
            if temp_engine is not None:
                await temp_engine.dispose()

    @staticmethod
    def _validate_query(sql: str) -> None:
        """Reject any statement containing DDL/DML keywords.

        Raises:
            ValueError: if a blocked keyword is found.
        """
        lowered = sql.lower()
        for kw in _BLOCKED_KEYWORDS:
            if kw in lowered:
                raise ValueError(
                    f"Blocked keyword '{kw}' detected. Only SELECT statements are permitted."
                )

    async def execute_safe(
        self, session: AsyncSession, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SQL string with read-only guardrails.

        Applies:
        - Keyword block-list (no DDL/DML).
        - Row limit cap (QUERY_ROW_LIMIT).

        Returns:
            A list of row dicts (column_name -> value), capped at QUERY_ROW_LIMIT.
        """
        self._validate_query(sql)
        stmt = text(sql)
        result = await session.execute(stmt, params or {})
        rows = result.mappings().fetchmany(QUERY_ROW_LIMIT)
        return [dict(row) for row in rows]

    async def dispose(self, project_id: uuid.UUID, connection_id: uuid.UUID) -> None:
        """Dispose and remove a pooled engine (e.g. on connection delete)."""
        key = (project_id, connection_id)
        engine = self._engines.pop(key, None)
        if engine:
            await engine.dispose()

    async def dispose_all(self) -> None:
        """Dispose all pooled engines (e.g. on app shutdown)."""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()


# Application-scoped singleton — injected via FastAPI dependency
connection_manager = ConnectionManager()
