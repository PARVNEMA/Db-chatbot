"""
SemanticLayer domain — service layer.

Orchestrates business logic for user-defined semantic annotations (table and column descriptions).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies.auth import DbSession
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.semantic_layer.models import SchemaAnnotation
from app.domain.semantic_layer.repository import SchemaAnnotationRepository
from app.domain.semantic_layer.schemas import AnnotationCreate, AnnotationUpdate

logger = logging.getLogger(__name__)


class SemanticLayerService:
    """Domain service managing table and column annotations."""

    def __init__(
        self,
        db: AsyncSession,
        connection_service: ConnectionService,
    ) -> None:
        self._db = db
        self._connection_service = connection_service
        self._repo = SchemaAnnotationRepository(db)

    async def create_annotation(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AnnotationCreate,
    ) -> SchemaAnnotation:
        """Create a new schema annotation after verifying project ownership."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        annotation = await self._repo.create_annotation(
            project_id=project_id,
            connection_id=connection.id,
            target_type=data.target_type,
            note=data.note,
            schema_table_id=data.schema_table_id,
            schema_column_id=data.schema_column_id,
            is_auto_generated=data.is_auto_generated,
        )
        logger.info(
            "Created annotation %s for project %s (%s)",
            annotation.id,
            project_id,
            data.target_type,
        )
        await self._sync_embeddings_for_annotation(
            project_id=project_id, connection_id=connection.id, annotation=annotation
        )
        return annotation

    async def get_annotation(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        annotation_id: uuid.UUID,
    ) -> SchemaAnnotation:
        """Fetch a single annotation ensuring project ownership."""
        await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        annotation = await self._repo.get_annotation(
            project_id=project_id, annotation_id=annotation_id
        )
        if annotation is None:
            raise NotFoundException(
                detail=f"Annotation '{annotation_id}' not found.",
                error_code="ANNOTATION_NOT_FOUND",
            )
        return annotation

    async def list_annotations(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        target_type: str | None = None,
    ) -> Sequence[SchemaAnnotation]:
        """List all annotations for the project's active connection."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        return await self._repo.get_annotations_for_connection(
            project_id=project_id,
            connection_id=connection.id,
            target_type=target_type,
        )

    async def update_annotation(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        annotation_id: uuid.UUID,
        data: AnnotationUpdate,
    ) -> SchemaAnnotation:
        """Update an existing schema annotation."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        annotation = await self._repo.update_annotation(
            project_id=project_id,
            annotation_id=annotation_id,
            note=data.note,
        )
        if annotation is None:
            raise NotFoundException(
                detail=f"Annotation '{annotation_id}' not found.",
                error_code="ANNOTATION_NOT_FOUND",
            )
        logger.info("Updated annotation %s for project %s", annotation_id, project_id)
        await self._sync_embeddings_for_annotation(
            project_id=project_id, connection_id=connection.id, annotation=annotation
        )
        return annotation

    async def delete_annotation(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        annotation_id: uuid.UUID,
    ) -> None:
        """Delete a schema annotation."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )
        annotation = await self._repo.get_annotation(
            project_id=project_id, annotation_id=annotation_id
        )
        if annotation is None:
            raise NotFoundException(
                detail=f"Annotation '{annotation_id}' not found.",
                error_code="ANNOTATION_NOT_FOUND",
            )
        deleted = await self._repo.delete_annotation(
            project_id=project_id, annotation_id=annotation_id
        )
        if not deleted:
            raise NotFoundException(
                detail=f"Annotation '{annotation_id}' not found.",
                error_code="ANNOTATION_NOT_FOUND",
            )
        logger.info("Deleted annotation %s for project %s", annotation_id, project_id)
        await self._sync_embeddings_for_annotation(
            project_id=project_id, connection_id=connection.id, annotation=annotation
        )

    async def _sync_embeddings_for_annotation(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        annotation: SchemaAnnotation,
    ) -> None:
        """Sync vector embeddings after annotation mutations."""
        try:
            from app.domain.embeddings.services import EmbeddingService

            emb_service = EmbeddingService(
                db=self._db, connection_service=self._connection_service
            )
            if annotation.schema_column_id:
                await emb_service.regenerate_for_column(
                    project_id=project_id,
                    connection_id=connection_id,
                    column_id=annotation.schema_column_id,
                )
            elif annotation.schema_table_id:
                await emb_service.generate_and_store_for_connection(
                    project_id=project_id,
                    connection_id=connection_id,
                )
        except Exception as exc:
            logger.warning(
                "Embedding sync skipped/failed for project %s: %s", project_id, exc
            )


def get_semantic_layer_service(
    db: DbSession,
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> SemanticLayerService:
    """FastAPI dependency provider for SemanticLayerService."""
    return SemanticLayerService(db=db, connection_service=connection_service)
