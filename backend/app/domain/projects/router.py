"""
Projects domain — FastAPI router.

Exposes REST endpoints for project CRUD operations.
Mounted under `/api/v1/projects` in `app/main.py`.
All endpoints enforce user authentication and multi-tenant isolation.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import (
    ApiResponse,
    PaginatedData,
    paginated_response,
    success_response,
)
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import Pagination
from app.domain.auth.models import User
from app.domain.projects.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.domain.projects.services import ProjectService, get_project_service

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    description="Create a project scoped to the currently authenticated user.",
)
async def create_project(
    data: ProjectCreate,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ProjectResponse]:
    """Create a new project owned by current active user."""
    project = await service.create_project(data=data, owner_id=current_user.id)
    return success_response(
        data=ProjectResponse.model_validate(project),
        message="Project created successfully",
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedData[ProjectResponse]],
    status_code=status.HTTP_200_OK,
    summary="List user projects",
    description="Retrieve a paginated list of projects owned by the currently authenticated user.",
)
async def list_projects(
    pagination: Pagination,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[PaginatedData[ProjectResponse]]:
    """List all projects belonging to the current active user with pagination."""
    items, total = await service.list_projects(owner_id=current_user.id, pagination=pagination)
    return paginated_response(
        items=[ProjectResponse.model_validate(p) for p in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        message="Projects retrieved successfully",
    )


@router.get(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Get project details",
    description="Retrieve detailed information for a specific project.",
)
async def get_project(
    project_id: uuid.UUID,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ProjectResponse]:
    """Get project by ID if owned by the current active user."""
    project = await service.get_project(project_id=project_id, owner_id=current_user.id)
    return success_response(
        data=ProjectResponse.model_validate(project),
        message="Project retrieved successfully",
    )


@router.patch(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description="Update name or description of an existing project.",
)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ProjectResponse]:
    """Update project details if owned by the current active user."""
    project = await service.update_project(
        project_id=project_id, data=data, owner_id=current_user.id
    )
    return success_response(
        data=ProjectResponse.model_validate(project),
        message="Project updated successfully",
    )


@router.delete(
    "/{project_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete project",
    description="Delete a project and cascade delete all associated resources.",
)
async def delete_project(
    project_id: uuid.UUID,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[None]:
    """Delete project if owned by the current active user."""
    await service.delete_project(project_id=project_id, owner_id=current_user.id)
    return success_response(
        data=None,
        message="Project deleted successfully",
    )
