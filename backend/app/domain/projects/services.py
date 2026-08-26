"""
Projects domain — service layer.

Orchestrates business logic, transaction boundaries, and delegates persistence
to `ProjectRepository`. Enforces tenant boundaries and domain exceptions.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies.auth import DbSession
from app.dependencies.pagination import PaginationParams
from app.domain.projects.models import Project
from app.domain.projects.repository import ProjectRepository
from app.domain.projects.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    """Domain service managing project workflows and multi-tenant isolation."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ProjectRepository(db)

    async def create_project(self, data: ProjectCreate, owner_id: uuid.UUID) -> Project:
        """Create a new project for the authenticated user."""
        return await self._repo.create(owner_id=owner_id, payload=data)

    async def get_project(self, project_id: uuid.UUID, owner_id: uuid.UUID) -> Project:
        """Retrieve a project by ID ensuring ownership."""
        project = await self._repo.get_by_id(project_id=project_id, owner_id=owner_id)
        if project is None:
            raise NotFoundException(
                detail=f"Project with ID '{project_id}' was not found.",
                error_code="PROJECT_NOT_FOUND",
            )
        return project

    async def list_projects(
        self, owner_id: uuid.UUID, pagination: PaginationParams
    ) -> tuple[list[Project], int]:
        """List paginated projects belonging to the owner."""
        return await self._repo.list_by_owner(
            owner_id=owner_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

    async def update_project(
        self, project_id: uuid.UUID, data: ProjectUpdate, owner_id: uuid.UUID
    ) -> Project:
        """Update an existing project after validating ownership."""
        project = await self.get_project(project_id=project_id, owner_id=owner_id)
        return await self._repo.update(project=project, payload=data)

    async def delete_project(self, project_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        """Delete a project after validating ownership."""
        project = await self.get_project(project_id=project_id, owner_id=owner_id)
        await self._repo.delete(project=project)


def get_project_service(db: DbSession) -> ProjectService:
    """FastAPI dependency provider for ProjectService."""
    return ProjectService(db=db)
