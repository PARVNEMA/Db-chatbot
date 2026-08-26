"""
Connections domain — FastAPI router.

Exposes REST endpoints for tenant database connection configuration.
Mounted under `/api/v1/projects` in `app/main.py`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ApiResponse, success_response
from app.dependencies.auth import get_current_active_user
from app.domain.auth.models import User
from app.domain.connections.schemas import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionUpdate,
)
from app.domain.connections.services import ConnectionService, get_connection_service

router = APIRouter()


@router.post(
    "/{project_id}/connections",
    response_model=ApiResponse[ConnectionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create project database connection",
    description="Securely save and verify an encrypted target database connection for a project.",
)
async def create_connection(
    project_id: uuid.UUID,
    data: ConnectionCreate,
    service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ConnectionResponse]:
    """Create and test a new database connection for the project."""
    connection = await service.create_connection(
        project_id=project_id, data=data, user_id=current_user.id
    )
    return success_response(
        data=ConnectionResponse.model_validate(connection),
        message="Connection established and saved successfully",
    )


@router.get(
    "/{project_id}/connections",
    response_model=ApiResponse[ConnectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get project database connection",
    description="Retrieve connection metadata for the project (credentials are omitted).",
)
async def get_connection(
    project_id: uuid.UUID,
    service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ConnectionResponse]:
    """Fetch configured database connection for the project."""
    connection = await service.get_connection(project_id=project_id, user_id=current_user.id)
    return success_response(
        data=ConnectionResponse.model_validate(connection),
        message="Connection retrieved successfully",
    )


@router.patch(
    "/{project_id}/connections",
    response_model=ApiResponse[ConnectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Update project database connection",
    description="Update connection name, dialect, or connection string.",
)
async def update_connection(
    project_id: uuid.UUID,
    data: ConnectionUpdate,
    service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ConnectionResponse]:
    """Update connection details for the project."""
    connection = await service.update_connection(
        project_id=project_id, data=data, user_id=current_user.id
    )
    return success_response(
        data=ConnectionResponse.model_validate(connection),
        message="Connection updated successfully",
    )


@router.delete(
    "/{project_id}/connections",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete project database connection",
    description="Remove the database connection and dispose all pooled connections.",
)
async def delete_connection(
    project_id: uuid.UUID,
    service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[None]:
    """Delete configured database connection for the project."""
    await service.delete_connection(project_id=project_id, user_id=current_user.id)
    return success_response(
        data=None,
        message="Connection deleted successfully",
    )


@router.post(
    "/{project_id}/connections/test",
    response_model=ApiResponse[ConnectionTestResponse],
    status_code=status.HTTP_200_OK,
    summary="Test target database connectivity",
    description="Test connection using provided credentials or existing saved credentials.",
)
async def test_connection(
    project_id: uuid.UUID,
    service: Annotated[ConnectionService, Depends(get_connection_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    data: ConnectionTestRequest | None = None,
) -> ApiResponse[ConnectionTestResponse]:
    """Test connectivity to target database."""
    test_result = await service.test_connection_params(
        project_id=project_id, user_id=current_user.id, payload=data
    )
    return success_response(
        data=test_result,
        message=test_result.message,
    )
