"""
Connections domain — repository layer.

All database access for `Connection` entities is centralised here.
Queries strictly enforce project isolation via `project_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.connections.models import Connection


class ConnectionRepository:
    """Data access layer for Connection entities."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        dialect: str,
        encrypted_connection_string: str,
    ) -> Connection:
        """Create a new Connection record for a project."""
        connection = Connection(
            project_id=project_id,
            name=name,
            dialect=dialect,
            encrypted_connection_string=encrypted_connection_string,
        )
        self._db.add(connection)
        await self._db.flush()
        await self._db.refresh(connection)
        return connection

    async def get_by_project_id(self, project_id: uuid.UUID) -> Connection | None:
        """Fetch connection for a project."""
        stmt = select(Connection).where(Connection.project_id == project_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(
        self, connection_id: uuid.UUID, project_id: uuid.UUID | None = None
    ) -> Connection | None:
        """Fetch a single connection by ID, optionally scoped by project_id."""
        stmt = select(Connection).where(Connection.id == connection_id)
        if project_id is not None:
            stmt = stmt.where(Connection.project_id == project_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        connection: Connection,
        name: str | None = None,
        dialect: str | None = None,
        encrypted_connection_string: str | None = None,
        writes_enabled: bool | None = None,
        max_insert_rows_per_table: int | None = None,
        max_patch_rows_per_table: int | None = None,
        max_total_rows_per_changeset: int | None = None,
        max_tables_per_changeset: int | None = None,
        approval_timeout_minutes: int | None = None,
        undo_window_minutes: int | None = None,
        blocked_tables: list[str] | None = None,
    ) -> Connection:
        """Update connection attributes."""
        if name is not None:
            connection.name = name
        if dialect is not None:
            connection.dialect = dialect
        if encrypted_connection_string is not None:
            connection.encrypted_connection_string = encrypted_connection_string
        if writes_enabled is not None:
            connection.writes_enabled = writes_enabled
        if max_insert_rows_per_table is not None:
            connection.max_insert_rows_per_table = max_insert_rows_per_table
        if max_patch_rows_per_table is not None:
            connection.max_patch_rows_per_table = max_patch_rows_per_table
        if max_total_rows_per_changeset is not None:
            connection.max_total_rows_per_changeset = max_total_rows_per_changeset
        if max_tables_per_changeset is not None:
            connection.max_tables_per_changeset = max_tables_per_changeset
        if approval_timeout_minutes is not None:
            connection.approval_timeout_minutes = approval_timeout_minutes
        if undo_window_minutes is not None:
            connection.undo_window_minutes = undo_window_minutes
        if blocked_tables is not None:
            connection.blocked_tables = blocked_tables

        await self._db.flush()
        await self._db.refresh(connection)
        return connection

    async def delete(self, connection: Connection) -> None:
        """Delete connection from database."""
        await self._db.delete(connection)
        await self._db.flush()
