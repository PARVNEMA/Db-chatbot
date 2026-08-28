"""
Embeddings domain — FastAPI router.

Exposes REST endpoints for schema vector search and triggering embedding generation.
Mounted under `/api/v1/projects` in `app/main.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.config import get_settings
from app.core.responses import ApiResponse, success_response
from app.dependencies.auth import get_current_active_user
from app.domain.auth.models import User
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.embeddings.schemas import (
    AutoSuggestResponse,
    EmbeddingGenerateResponse,
    SchemaSearchRequest,
    SchemaSearchResult,
)
from app.domain.embeddings.services import (
    EmbeddingService,
    get_embedding_service,
)

router = APIRouter()


@router.post(
    "/{project_id}/schema/search",
    response_model=ApiResponse[list[SchemaSearchResult]],
    status_code=status.HTTP_200_OK,
    summary="Semantic vector search over schema",
    description="Retrieve the most relevant database columns and tables for a given natural language query.",
)
async def search_schema(
    project_id: uuid.UUID,
    payload: SchemaSearchRequest,
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[list[SchemaSearchResult]]:
    """Search schema columns by natural language query."""
    results = await service.search_schema(
        project_id=project_id,
        user_id=current_user.id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return success_response(
        data=results,
        message="Schema search completed successfully",
    )


@router.post(
    "/{project_id}/schema/embeddings/generate",
    response_model=ApiResponse[EmbeddingGenerateResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate vector embeddings for introspected schema",
    description="Construct composite embed_text for all tables/columns in the project and store their vectors in pgvector.",
)
async def generate_embeddings(
    project_id: uuid.UUID,
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    conn_service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[EmbeddingGenerateResponse]:
    """Generate vector embeddings for all columns in the connection schema."""
    settings = get_settings()
    connection = await conn_service.get_connection(project_id=project_id, user_id=current_user.id)
    count = await service.generate_and_store_for_connection(
        project_id=project_id, connection_id=connection.id
    )
    response_data = EmbeddingGenerateResponse(
        project_id=project_id,
        connection_id=connection.id,
        embedded_columns_count=count,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
    return success_response(
        data=response_data,
        message=f"Successfully generated embeddings for {count} columns",
    )


@router.post(
    "/{project_id}/schema/auto-suggest",
    response_model=ApiResponse[AutoSuggestResponse],
    status_code=status.HTTP_200_OK,
    summary="Auto-suggest table and column descriptions via LLM",
    description="Use configured LLM to generate initial draft business descriptions for schema tables and columns.",
)
async def auto_suggest_descriptions(
    project_id: uuid.UUID,
    service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[AutoSuggestResponse]:
    """Trigger LLM auto-suggest for schema annotations."""
    result = await service.auto_suggest_descriptions(
        project_id=project_id, user_id=current_user.id
    )
    return success_response(
        data=result,
        message=(
            f"Auto-suggest generated {result.suggested_tables_count} table descriptions "
            f"and {result.suggested_columns_count} column descriptions"
        ),
    )
