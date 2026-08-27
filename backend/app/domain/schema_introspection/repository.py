"""
SchemaIntrospection domain — repository layer.

Handles all persistence operations for `SchemaCache`, `SchemaTable`,
and `SchemaColumn` entities with strict `project_id` tenant isolation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.schema_introspection.models import SchemaCache, SchemaColumn, SchemaTable


class SchemaIntrospectionRepository:
    """Data access layer for introspected schema caches, tables, and columns."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_cache(
        self, project_id: uuid.UUID, connection_id: uuid.UUID
    ) -> SchemaCache | None:
        """Fetch the full SchemaCache record including loaded tables and columns."""
        stmt = (
            select(SchemaCache)
            .where(
                SchemaCache.project_id == project_id,
                SchemaCache.connection_id == connection_id,
            )
            .options(
                selectinload(SchemaCache.tables).selectinload(SchemaTable.columns)
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tables(
        self, project_id: uuid.UUID, connection_id: uuid.UUID
    ) -> list[SchemaTable]:
        """Fetch all introspected tables with their columns for a given connection."""
        stmt = (
            select(SchemaTable)
            .where(
                SchemaTable.project_id == project_id,
                SchemaTable.connection_id == connection_id,
            )
            .options(selectinload(SchemaTable.columns))
            .order_by(SchemaTable.table_name)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_table_by_name(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        table_name: str,
        schema_name: str | None = None,
    ) -> SchemaTable | None:
        """Fetch a specific table by name along with its ordered columns."""
        stmt = (
            select(SchemaTable)
            .where(
                SchemaTable.project_id == project_id,
                SchemaTable.connection_id == connection_id,
                SchemaTable.table_name == table_name,
            )
            .options(selectinload(SchemaTable.columns))
        )
        if schema_name is not None:
            stmt = stmt.where(SchemaTable.schema_name == schema_name)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_introspected_schema(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        raw_schema: dict[str, Any],
        tables_data: list[dict[str, Any]],
    ) -> SchemaCache:
        """Atomically persist introspected raw JSON cache and normalized tables & columns."""
        # 1. Clean up any existing columns, tables, and cache for this connection
        delete_cols_stmt = delete(SchemaColumn).where(
            SchemaColumn.project_id == project_id,
            SchemaColumn.connection_id == connection_id,
        )
        await self._db.execute(delete_cols_stmt)

        delete_tables_stmt = delete(SchemaTable).where(
            SchemaTable.project_id == project_id,
            SchemaTable.connection_id == connection_id,
        )
        await self._db.execute(delete_tables_stmt)

        delete_cache_stmt = delete(SchemaCache).where(
            SchemaCache.project_id == project_id,
            SchemaCache.connection_id == connection_id,
        )
        await self._db.execute(delete_cache_stmt)
        await self._db.flush()

        # 2. Construct new SchemaCache entity
        now = datetime.now(tz=UTC)
        cache = SchemaCache(
            project_id=project_id,
            connection_id=connection_id,
            introspected_at=now,
            raw_schema=raw_schema,
        )
        self._db.add(cache)
        await self._db.flush()
        await self._db.refresh(cache)

        # 3. Construct and append SchemaTable + SchemaColumn entities
        for t_info in tables_data:
            table = SchemaTable(
                cache_id=cache.id,
                project_id=project_id,
                connection_id=connection_id,
                schema_name=t_info.get("schema_name"),
                table_name=t_info["table_name"],
            )
            self._db.add(table)
            await self._db.flush()
            await self._db.refresh(table)

            for col_info in t_info.get("columns", []):
                column = SchemaColumn(
                    table_id=table.id,
                    project_id=project_id,
                    connection_id=connection_id,
                    column_name=col_info["name"],
                    data_type=col_info["type"],
                    is_nullable=col_info.get("nullable", True),
                    is_primary_key=col_info.get("is_primary_key", False),
                    is_foreign_key=col_info.get("is_foreign_key", False),
                    fk_target_table=col_info.get("fk_target_table"),
                    fk_target_column=col_info.get("fk_target_column"),
                    ordinal_position=col_info.get("ordinal_position", 0),
                )
                self._db.add(column)

        await self._db.flush()

        # 4. Fetch the full newly saved cache with all relationships
        saved_cache = await self.get_cache(project_id=project_id, connection_id=connection_id)
        assert saved_cache is not None
        return saved_cache

    async def delete_cache(self, project_id: uuid.UUID, connection_id: uuid.UUID) -> None:
        """Delete schema cache and associated tables/columns."""
        stmt = delete(SchemaCache).where(
            SchemaCache.project_id == project_id,
            SchemaCache.connection_id == connection_id,
        )
        await self._db.execute(stmt)
        await self._db.flush()

