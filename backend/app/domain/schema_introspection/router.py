"""
SchemaIntrospection domain — FastAPI router.

Exposes REST endpoints for triggering schema introspection, retrieving
schema overviews, and querying introspected table/column metadata.
Mounted under `/api/v1/projects` in `app/main.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ApiResponse, success_response
from app.dependencies.auth import get_current_active_user
from app.domain.auth.models import User
from app.domain.schema_introspection.schemas import (
    IntrospectResponse,
    SchemaOverviewResponse,
    TableDetailResponse,
)
from app.domain.schema_introspection.services import (
    SchemaIntrospectionService,
    get_schema_introspection_service,
)

router = APIRouter()


@router.post(
    "/{project_id}/schema/introspect",
    response_model=ApiResponse[IntrospectResponse],
    status_code=status.HTTP_200_OK,
    summary="Trigger target database schema introspection",
    description="Connect to the target database, reflect its schema, and persist normalized metadata and raw JSON cache.",
)
async def introspect_schema(
    project_id: uuid.UUID,
    service: Annotated[
        SchemaIntrospectionService, Depends(get_schema_introspection_service)
    ],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[IntrospectResponse]:
    """Trigger live target database introspection."""
    result = await service.introspect_schema(
        project_id=project_id, user_id=current_user.id
    )
    return success_response(
        data=result,
        message="Schema introspection completed successfully",
    )


@router.get(
    "/{project_id}/schema",
    response_model=ApiResponse[SchemaOverviewResponse],
    status_code=status.HTTP_200_OK,
    summary="Get project schema overview",
    description="Fetch high-level introspected schema overview and table list for the project.",
)
async def get_schema_overview(
    project_id: uuid.UUID,
    service: Annotated[
        SchemaIntrospectionService, Depends(get_schema_introspection_service)
    ],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[SchemaOverviewResponse]:
    """Retrieve schema overview."""
    overview = await service.get_schema_overview(
        project_id=project_id, user_id=current_user.id
    )
    return success_response(
        data=overview,
        message="Schema overview retrieved successfully",
    )


@router.get(
    "/{project_id}/schema/tables",
    response_model=ApiResponse[list[TableDetailResponse]],
    status_code=status.HTTP_200_OK,
    summary="List all introspected tables and columns",
    description="Fetch all introspected tables and their associated columns for the project.",
)
async def list_tables(
    project_id: uuid.UUID,
    service: Annotated[
        SchemaIntrospectionService, Depends(get_schema_introspection_service)
    ],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[list[TableDetailResponse]]:
    """List tables with column details."""
    tables = await service.list_tables(project_id=project_id, user_id=current_user.id)
    return success_response(
        data=tables,
        message="Tables retrieved successfully",
    )


@router.get(
    "/{project_id}/schema/tables/{table_name}",
    response_model=ApiResponse[TableDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get specific table metadata",
    description="Fetch column metadata, primary key, and foreign key details for a specific table.",
)
async def get_table_detail(
    project_id: uuid.UUID,
    table_name: str,
    service: Annotated[
        SchemaIntrospectionService, Depends(get_schema_introspection_service)
    ],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[TableDetailResponse]:
    """Retrieve table details by table name."""
    table = await service.get_table(
        project_id=project_id, table_name=table_name, user_id=current_user.id
    )
    return success_response(
        data=table,
        message="Table details retrieved successfully",
    )

