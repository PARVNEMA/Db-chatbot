"""
SchemaIntrospection domain — service layer.

Orchestrates live target database reflection, extraction of tables,
columns, types, constraints, and persistence to `SchemaCache`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import inspect
from sqlalchemy.engine import Connection as SyncConnection
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies.auth import DbSession
from app.domain.connections.manager import ConnectionManager, connection_manager
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.schema_introspection.repository import SchemaIntrospectionRepository
from app.domain.schema_introspection.schemas import (
    ColumnResponse,
    IntrospectResponse,
    SchemaOverviewResponse,
    TableDetailResponse,
    TableResponse,
)

logger = logging.getLogger(__name__)


def _reflect_database_schema(
    sync_conn: SyncConnection,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Synchronous reflection callable executed inside `conn.run_sync()`.

    Returns:
        (raw_schema_dict, normalized_tables_list)
    """
    inspector = inspect(sync_conn)
    default_schema = inspector.default_schema_name

    table_names = inspector.get_table_names()

    raw_tables: dict[str, Any] = {}
    normalized_tables: list[dict[str, Any]] = []

    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name) or {}
        pk_columns = set(pk_constraint.get("constrained_columns") or [])

        fk_constraints = inspector.get_foreign_keys(table_name) or []
        fk_map: dict[str, dict[str, Any]] = {}
        for fk in fk_constraints:
            referred_table = fk.get("referred_table")
            constrained_cols = fk.get("constrained_columns") or []
            referred_cols = fk.get("referred_columns") or []
            for i, col in enumerate(constrained_cols):
                target_col = referred_cols[i] if i < len(referred_cols) else None
                fk_map[col] = {
                    "is_foreign_key": True,
                    "fk_target_table": referred_table,
                    "fk_target_column": target_col,
                }

        col_list: list[dict[str, Any]] = []
        raw_col_list: list[dict[str, Any]] = []
        for idx, col in enumerate(columns):
            c_name = col["name"]
            c_type = str(col["type"])
            c_nullable = bool(col.get("nullable", True))
            is_pk = c_name in pk_columns
            fk_info = fk_map.get(c_name, {})
            is_fk = fk_info.get("is_foreign_key", False)
            fk_target_tbl = fk_info.get("fk_target_table")
            fk_target_col = fk_info.get("fk_target_column")

            col_data = {
                "name": c_name,
                "type": c_type,
                "nullable": c_nullable,
                "is_primary_key": is_pk,
                "is_foreign_key": is_fk,
                "fk_target_table": fk_target_tbl,
                "fk_target_column": fk_target_col,
                "ordinal_position": idx + 1,
            }
            col_list.append(col_data)
            raw_col_list.append(
                {
                    "name": c_name,
                    "type": c_type,
                    "nullable": c_nullable,
                    "default": str(col.get("default")) if col.get("default") is not None else None,
                    "primary_key": is_pk,
                }
            )

        raw_tables[table_name] = {
            "columns": raw_col_list,
            "primary_keys": list(pk_columns),
            "foreign_keys": fk_constraints,
        }

        normalized_tables.append(
            {
                "schema_name": default_schema,
                "table_name": table_name,
                "columns": col_list,
            }
        )

    raw_schema = {
        "dialect": sync_conn.dialect.name,
        "default_schema": default_schema,
        "tables": raw_tables,
    }
    return raw_schema, normalized_tables


class SchemaIntrospectionService:
    """Domain service managing schema introspection workflows and queries."""

    def __init__(
        self,
        db: AsyncSession,
        connection_service: ConnectionService,
        manager: ConnectionManager = connection_manager,
    ) -> None:
        self._db = db
        self._connection_service = connection_service
        self._manager = manager
        self._repo = SchemaIntrospectionRepository(db)

    async def introspect_schema(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> IntrospectResponse:
        """Reflect target database schema and atomically persist cache and normalized entities."""
        # 1. Fetch connection and ensure user ownership
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )

        # 2. Acquire connection engine and run reflection
        engine = self._manager.get_engine(
            project_id=project_id,
            connection_id=connection.id,
            encrypted_connection_string=connection.encrypted_connection_string,
        )

        try:
            async with engine.connect() as conn:
                raw_schema, tables_data = await conn.run_sync(_reflect_database_schema)
        except Exception as exc:
            logger.exception("Failed to reflect schema for connection %s: %s", connection.id, exc)
            raise BadRequestException(
                detail=f"Schema introspection failed on target database: {exc}",
                error_code="INTROSPECTION_FAILED",
            ) from exc

        # 3. Atomically save cache and normalized tables/columns
        saved_cache = await self._repo.save_introspected_schema(
            project_id=project_id,
            connection_id=connection.id,
            raw_schema=raw_schema,
            tables_data=tables_data,
        )

        # 4. Generate initial vector embeddings for the introspected schema
        try:
            from app.domain.embeddings.services import EmbeddingService

            embedding_service = EmbeddingService(
                db=self._db, connection_service=self._connection_service
            )
            await embedding_service.generate_and_store_for_connection(
                project_id=project_id, connection_id=connection.id
            )
        except Exception as emb_exc:
            logger.warning(
                "Initial embedding generation skipped/failed for connection %s: %s",
                connection.id,
                emb_exc,
            )

        # 5. Construct IntrospectResponse
        total_cols = sum(len(t.columns) for t in saved_cache.tables)
        table_details = [
            TableDetailResponse(
                id=t.id,
                connection_id=t.connection_id,
                project_id=t.project_id,
                schema_name=t.schema_name,
                table_name=t.table_name,
                columns=[ColumnResponse.model_validate(c) for c in t.columns],
                created_at=t.created_at,
            )
            for t in saved_cache.tables
        ]

        return IntrospectResponse(
            connection_id=connection.id,
            project_id=project_id,
            introspected_at=saved_cache.introspected_at,
            table_count=len(saved_cache.tables),
            column_count=total_cols,
            tables=table_details,
        )

    async def get_schema_overview(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> SchemaOverviewResponse:
        """Fetch summary of the introspected schema."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        cache = await self._repo.get_cache(
            project_id=project_id, connection_id=connection.id
        )
        if cache is None:
            raise NotFoundException(
                detail=f"No introspected schema found for project '{project_id}'. Run introspection first.",
                error_code="SCHEMA_NOT_INTROSPECTED",
            )

        table_responses = [
            TableResponse(
                id=t.id,
                connection_id=t.connection_id,
                project_id=t.project_id,
                schema_name=t.schema_name,
                table_name=t.table_name,
                column_count=len(t.columns),
                created_at=t.created_at,
            )
            for t in cache.tables
        ]

        return SchemaOverviewResponse(
            connection_id=connection.id,
            project_id=project_id,
            introspected_at=cache.introspected_at,
            table_count=len(cache.tables),
            tables=table_responses,
        )

    async def list_tables(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[TableDetailResponse]:
        """Fetch all introspected tables with their columns."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        tables = await self._repo.get_tables(
            project_id=project_id, connection_id=connection.id
        )
        return [
            TableDetailResponse(
                id=t.id,
                connection_id=t.connection_id,
                project_id=t.project_id,
                schema_name=t.schema_name,
                table_name=t.table_name,
                columns=[ColumnResponse.model_validate(c) for c in t.columns],
                created_at=t.created_at,
            )
            for t in tables
        ]

    async def get_table(
        self,
        project_id: uuid.UUID,
        table_name: str,
        user_id: uuid.UUID,
        schema_name: str | None = None,
    ) -> TableDetailResponse:
        """Fetch details for a single table."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        table = await self._repo.get_table_by_name(
            project_id=project_id,
            connection_id=connection.id,
            table_name=table_name,
            schema_name=schema_name,
        )
        if table is None:
            raise NotFoundException(
                detail=f"Table '{table_name}' not found in introspected schema.",
                error_code="TABLE_NOT_FOUND",
            )

        return TableDetailResponse(
            id=table.id,
            connection_id=table.connection_id,
            project_id=table.project_id,
            schema_name=table.schema_name,
            table_name=table.table_name,
            columns=[ColumnResponse.model_validate(c) for c in table.columns],
            created_at=table.created_at,
        )


def get_schema_introspection_service(
    db: DbSession,
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> SchemaIntrospectionService:
    """FastAPI dependency provider for SchemaIntrospectionService."""
    return SchemaIntrospectionService(db=db, connection_service=connection_service)

