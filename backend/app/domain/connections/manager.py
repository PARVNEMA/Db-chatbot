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
from datetime import date, datetime
from datetime import time as time_type
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import decrypt

# Default connection timeout in seconds for target DBs
CONNECT_TIMEOUT_SECONDS: float = 10.0
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


def serialize_row_value(val: Any) -> Any:
    """Convert database column values to JSON-serializable primitives."""
    if val is None:
        return None
    if isinstance(val, (datetime, date, time_type)):
        return val.isoformat()
    if isinstance(val, (Decimal, uuid.UUID)):
        return str(val)
    if isinstance(val, (bytes, bytearray, memoryview)):
        return bytes(val).hex()
    return val


def _build_connect_args(
    normalized_url: str, timeout_seconds: float = CONNECT_TIMEOUT_SECONDS
) -> dict[str, Any]:
    """Build dialect-specific connect_args with appropriate timeout parameters.

    - asyncpg (PostgreSQL): uses ``timeout`` (seconds, float).
    - asyncmy (MySQL/MariaDB): uses ``connect_timeout`` (seconds, int).
    - aiosqlite (SQLite): no timeout args needed.
    """
    if "asyncpg" in normalized_url:
        return {"timeout": float(timeout_seconds)}
    if "asyncmy" in normalized_url:
        return {"connect_timeout": int(timeout_seconds)}
    return {}


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
                pool_recycle=3600,
                connect_args=_build_connect_args(normalized_url),
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
        timeout_seconds: float = CONNECT_TIMEOUT_SECONDS,
    ) -> tuple[bool, float | None, str | None, str]:
        """Test database connectivity with the provided connection string.

        Returns:
            (success, latency_ms, dialect, message)
        """
        temp_engine: AsyncEngine | None = None
        try:
            normalized_url = normalize_connection_url(connection_string)

            temp_engine = create_async_engine(
                normalized_url,
                pool_pre_ping=True,
                connect_args=_build_connect_args(normalized_url, timeout_seconds),
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
        """Reject any statement containing DDL/DML keywords or non-SELECT AST.

        Raises:
            ValueError: if a blocked keyword or invalid AST is found.
        """
        from app.domain.agent.sql_validator import validate_read_only

        # Fast keyword check
        lowered = sql.lower()
        for kw in _BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", lowered):
                raise ValueError(
                    f"Blocked keyword '{kw}' detected. Only SELECT statements are permitted."
                )

        # Full AST-level validation
        validate_read_only(sql)

    async def execute_safe(
        self,
        session: AsyncSession,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout_seconds: float = QUERY_TIMEOUT_SECONDS,
    ) -> list[dict[str, Any]]:
        """Execute a SQL string with read-only guardrails, timeout, and row limits.

        Applies:
        - Keyword block-list and AST validation (no DDL/DML).
        - Execution timeout via asyncio.wait_for.
        - Row limit cap (QUERY_ROW_LIMIT).
        - Type serialization for JSON-compatible response shapes.

        Returns:
            A list of row dicts (column_name -> value), capped at QUERY_ROW_LIMIT.
        """
        self._validate_query(sql)
        stmt = text(sql)

        async def _run_query() -> list[dict[str, Any]]:
            result = await session.execute(stmt, params or {})
            raw_rows = result.mappings().fetchmany(QUERY_ROW_LIMIT)
            return [
                {k: serialize_row_value(v) for k, v in row.items()}
                for row in raw_rows
            ]

        return await asyncio.wait_for(_run_query(), timeout=timeout_seconds)

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
