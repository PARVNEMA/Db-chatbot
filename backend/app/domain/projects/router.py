"""
Projects domain — FastAPI router.

All routes are mounted under `/api/v1/projects` by `app/main.py`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domain.projects.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.domain.projects.services import ProjectService

router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    service: Annotated[ProjectService, Depends()],
) -> ProjectResponse:
    project = await service.create_project(payload)
    return ProjectResponse.model_validate(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    service: Annotated[ProjectService, Depends()],
) -> list[ProjectResponse]:
    projects = await service.list_projects()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    service: Annotated[ProjectService, Depends()],
) -> ProjectResponse:
    project = await service.get_project_or_404(project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    service: Annotated[ProjectService, Depends()],
) -> ProjectResponse:
    project = await service.update_project(project_id, payload)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    service: Annotated[ProjectService, Depends()],
) -> None:
    await service.delete_project(project_id)
