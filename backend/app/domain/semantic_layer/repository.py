"""
SemanticLayer domain — repository layer.

Handles data access and persistence for `SchemaAnnotation` entities with
strict multi-tenant isolation by `project_id`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.semantic_layer.models import SchemaAnnotation


class SchemaAnnotationRepository:
    """Data access layer for table and column annotations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_annotation(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        target_type: str,
        note: str,
        schema_table_id: uuid.UUID | None = None,
        schema_column_id: uuid.UUID | None = None,
        is_auto_generated: bool = False,
    ) -> SchemaAnnotation:
        """Create and persist a new schema annotation."""
        annotation = SchemaAnnotation(
            project_id=project_id,
            connection_id=connection_id,
            target_type=target_type,
            note=note,
            schema_table_id=schema_table_id,
            schema_column_id=schema_column_id,
            is_auto_generated=is_auto_generated,
        )
        self._db.add(annotation)
        await self._db.commit()
        await self._db.refresh(annotation)
        return annotation

    async def get_annotation(
        self, project_id: uuid.UUID, annotation_id: uuid.UUID
    ) -> SchemaAnnotation | None:
        """Fetch a single annotation by ID scoped to project_id."""
        stmt = select(SchemaAnnotation).where(
            SchemaAnnotation.project_id == project_id,
            SchemaAnnotation.id == annotation_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_annotations_for_connection(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        target_type: str | None = None,
    ) -> Sequence[SchemaAnnotation]:
        """Fetch all annotations for a database connection, optionally filtered by target_type."""
        stmt = (
            select(SchemaAnnotation)
            .where(
                SchemaAnnotation.project_id == project_id,
                SchemaAnnotation.connection_id == connection_id,
            )
            .order_by(SchemaAnnotation.created_at.asc())
        )
        if target_type is not None:
            stmt = stmt.where(SchemaAnnotation.target_type == target_type)
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_annotations_for_table(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        schema_table_id: uuid.UUID,
    ) -> Sequence[SchemaAnnotation]:
        """Fetch table-level annotations for a specific table."""
        stmt = (
            select(SchemaAnnotation)
            .where(
                SchemaAnnotation.project_id == project_id,
                SchemaAnnotation.connection_id == connection_id,
                SchemaAnnotation.schema_table_id == schema_table_id,
            )
            .order_by(SchemaAnnotation.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_annotation_for_column(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        schema_column_id: uuid.UUID,
    ) -> SchemaAnnotation | None:
        """Fetch annotation for a specific column."""
        stmt = select(SchemaAnnotation).where(
            SchemaAnnotation.project_id == project_id,
            SchemaAnnotation.connection_id == connection_id,
            SchemaAnnotation.schema_column_id == schema_column_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_annotation(
        self,
        project_id: uuid.UUID,
        annotation_id: uuid.UUID,
        note: str,
    ) -> SchemaAnnotation | None:
        """Update the note content of an existing annotation."""
        annotation = await self.get_annotation(
            project_id=project_id, annotation_id=annotation_id
        )
        if annotation is None:
            return None
        annotation.note = note
        await self._db.commit()
        await self._db.refresh(annotation)
        return annotation

    async def delete_annotation(
        self, project_id: uuid.UUID, annotation_id: uuid.UUID
    ) -> bool:
        """Delete an annotation by ID scoped to project_id."""
        annotation = await self.get_annotation(
            project_id=project_id, annotation_id=annotation_id
        )
        if annotation is None:
            return False
        await self._db.delete(annotation)
        await self._db.commit()
        return True

    async def delete_annotations_for_connection(
        self, project_id: uuid.UUID, connection_id: uuid.UUID
    ) -> int:
        """Delete all annotations for a connection."""
        stmt = delete(SchemaAnnotation).where(
            SchemaAnnotation.project_id == project_id,
            SchemaAnnotation.connection_id == connection_id,
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return result.rowcount  # type: ignore[return-value]
