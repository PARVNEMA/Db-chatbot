"""
Dynamic Multi-Tenant Connection Manager (ADR-0002).

Responsibilities:
- Decrypt Fernet-encrypted connection strings from the platform DB.
- Manage pooled SQLAlchemy async engines per (project_id, connection_id).
- Enforce read-only guardrails, execution timeouts, and row limit caps.

This is the ONLY place in the codebase where connection strings are decrypted.
Raw credentials MUST NOT be logged or surfaced elsewhere.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import decrypt

# Max rows returned per query execution
QUERY_ROW_LIMIT: int = 1000
# Query execution timeout in seconds
QUERY_TIMEOUT_SECONDS: int = 10

# DDL / DML keywords to block before execution
_BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {"insert", "update", "delete", "drop", "truncate", "alter", "create", "grant", "revoke"}
)


class ConnectionManager:
    """
    Manages pooled SQLAlchemy engines for tenant target databases.

    Usage:
        manager = ConnectionManager()
        async with manager.get_session(project_id, encrypted_conn_str) as session:
            result = await manager.execute_safe(session, sql_text)
    """

    def __init__(self) -> None:
        # Keyed by (project_id, connection_id) → AsyncEngine
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
            self._engines[key] = create_async_engine(
                plain_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return self._engines[key]

    def get_session(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        encrypted_connection_string: str,
    ) -> AsyncSession:
        """Return an AsyncSession bound to the tenant's target engine."""
        engine = self._get_or_create_engine(project_id, connection_id, encrypted_connection_string)
        SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return SessionLocal()  # type: ignore[return-value]

    @staticmethod
    def _validate_query(sql: str) -> None:
        """
        Reject any statement containing DDL/DML keywords.

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
        """
        Execute a SQL string with read-only guardrails.

        Applies:
        - Keyword block-list (no DDL/DML).
        - Row limit cap (QUERY_ROW_LIMIT).
        - TODO: execution timeout via asyncio.wait_for or DB-side SET statement_timeout.

        Returns:
            A list of row dicts (column_name → value), capped at QUERY_ROW_LIMIT.
        """
        self._validate_query(sql)
        from sqlalchemy import text

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
