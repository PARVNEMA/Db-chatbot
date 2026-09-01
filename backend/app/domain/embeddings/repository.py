"""
Embeddings domain — repository layer.

Handles persistence, upserts, deletions, and pgvector cosine similarity search
for `SchemaEmbedding` entities with strict multi-tenant `project_id` scoping.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.schema_introspection.models import SchemaColumn, SchemaEmbedding, SchemaTable


class EmbeddingRepository:
    """Data access layer for column vector embeddings."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_column_id(
        self, project_id: uuid.UUID, column_id: uuid.UUID
    ) -> SchemaEmbedding | None:
        """Fetch embedding for a specific column scoped to project_id."""
        stmt = select(SchemaEmbedding).where(
            SchemaEmbedding.project_id == project_id,
            SchemaEmbedding.schema_column_id == column_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_embedding(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        column_id: uuid.UUID,
        embed_text: str,
        embedding: list[float],
        model: str,
    ) -> SchemaEmbedding:
        """Insert or update a single column embedding."""
        existing = await self.get_by_column_id(project_id=project_id, column_id=column_id)
        if existing is not None:
            existing.embed_text = embed_text
            existing.embedding = embedding
            existing.model = model
            await self._db.commit()
            await self._db.refresh(existing)
            return existing

        record = SchemaEmbedding(
            project_id=project_id,
            connection_id=connection_id,
            schema_column_id=column_id,
            embed_text=embed_text,
            embedding=embedding,
            model=model,
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        return record

    async def bulk_save_embeddings(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        embeddings_data: list[dict[str, Any]],
    ) -> int:
        """Atomically replace all embeddings for a given connection."""
        # 1. Delete existing embeddings for this connection
        delete_stmt = delete(SchemaEmbedding).where(
            SchemaEmbedding.project_id == project_id,
            SchemaEmbedding.connection_id == connection_id,
        )
        await self._db.execute(delete_stmt)
        await self._db.flush()

        # 2. Add new embeddings
        for item in embeddings_data:
            rec = SchemaEmbedding(
                project_id=project_id,
                connection_id=connection_id,
                schema_column_id=item["column_id"],
                embed_text=item["embed_text"],
                embedding=item["embedding"],
                model=item["model"],
            )
            self._db.add(rec)

        await self._db.commit()
        return len(embeddings_data)

    async def delete_for_connection(
        self, project_id: uuid.UUID, connection_id: uuid.UUID
    ) -> int:
        """Delete all embeddings for a connection."""
        stmt = delete(SchemaEmbedding).where(
            SchemaEmbedding.project_id == project_id,
            SchemaEmbedding.connection_id == connection_id,
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return result.rowcount  # type: ignore[return-value]

    async def delete_for_column(
        self, project_id: uuid.UUID, column_id: uuid.UUID
    ) -> bool:
        """Delete embedding for a specific column."""
        stmt = delete(SchemaEmbedding).where(
            SchemaEmbedding.project_id == project_id,
            SchemaEmbedding.schema_column_id == column_id,
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return (result.rowcount or 0) > 0

    async def search_similar(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 15,
    ) -> list[dict[str, Any]]:
        """Search schema embeddings using pgvector cosine distance.

        Returns matching columns joined with table metadata and computed similarity score.
        """
        # Determine dialect
        bind = self._db.bind
        dialect_name = bind.dialect.name if bind is not None else "postgresql"

        if dialect_name == "sqlite":
            # For SQLite (in-memory test suite), compute in Python or fallback
            stmt = (
                select(SchemaEmbedding, SchemaColumn, SchemaTable)
                .join(SchemaColumn, SchemaEmbedding.schema_column_id == SchemaColumn.id)
                .join(SchemaTable, SchemaColumn.table_id == SchemaTable.id)
                .where(
                    SchemaEmbedding.project_id == project_id,
                    SchemaEmbedding.connection_id == connection_id,
                )
            )
            res = await self._db.execute(stmt)
            rows = res.all()
            results = []
            for emb, col, tbl in rows:
                results.append(
                    {
                        "column_id": col.id,
                        "table_id": tbl.id,
                        "schema_name": tbl.schema_name,
                        "table_name": tbl.table_name,
                        "column_name": col.column_name,
                        "data_type": col.data_type,
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key,
                        "fk_target_table": col.fk_target_table,
                        "fk_target_column": col.fk_target_column,
                        "embed_text": emb.embed_text,
                        "similarity_score": 1.0,
                    }
                )
            return results[:top_k]

        # PostgreSQL with pgvector cosine distance
        distance_expr = SchemaEmbedding.embedding.cosine_distance(query_embedding)
        stmt = (
            select(
                SchemaEmbedding,
                SchemaColumn,
                SchemaTable,
                distance_expr.label("distance"),
            )
            .join(SchemaColumn, SchemaEmbedding.schema_column_id == SchemaColumn.id)
            .join(SchemaTable, SchemaColumn.table_id == SchemaTable.id)
            .where(
                SchemaEmbedding.project_id == project_id,
                SchemaEmbedding.connection_id == connection_id,
            )
            .order_by(distance_expr.asc())
            .limit(top_k)
        )

        result = await self._db.execute(stmt)
        rows = result.all()

        output: list[dict[str, Any]] = []
        for emb, col, tbl, distance in rows:
            # Cosine similarity = 1 - distance (clamped to [0.0, 1.0])
            sim_score = max(0.0, min(1.0, 1.0 - float(distance)))
            output.append(
                {
                    "column_id": col.id,
                    "table_id": tbl.id,
                    "schema_name": tbl.schema_name,
                    "table_name": tbl.table_name,
                    "column_name": col.column_name,
                    "data_type": col.data_type,
                    "is_primary_key": col.is_primary_key,
                    "is_foreign_key": col.is_foreign_key,
                    "fk_target_table": col.fk_target_table,
                    "fk_target_column": col.fk_target_column,
                    "embed_text": emb.embed_text,
                    "similarity_score": round(sim_score, 4),
                }
            )
        return output
