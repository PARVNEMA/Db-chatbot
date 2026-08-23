"""
Projects domain — service layer.

Orchestrates business logic and delegates persistence to `ProjectRepository`.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domain.projects.models import Project
from app.domain.projects.repository import ProjectRepository
from app.domain.projects.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
        self._repo = ProjectRepository(db)

    async def create_project(self, payload: ProjectCreate) -> Project:
        return await self._repo.create(payload)

    async def get_project_or_404(self, project_id: uuid.UUID) -> Project:
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found.",
            )
        return project

    async def list_projects(self) -> list[Project]:
        return await self._repo.list_all()

    async def update_project(self, project_id: uuid.UUID, payload: ProjectUpdate) -> Project:
        project = await self.get_project_or_404(project_id)
        return await self._repo.update(project, payload)

    async def delete_project(self, project_id: uuid.UUID) -> None:
        project = await self.get_project_or_404(project_id)
        await self._repo.delete(project)
