"""
Projects domain — repository layer.

All database access for `Project` rows is centralised here.
Every query enforces tenant isolation by scoping to `owner_id`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.projects.models import Project
from app.domain.projects.schemas import ProjectCreate, ProjectUpdate


class ProjectRepository:
    """Data access layer for Project entities."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, owner_id: uuid.UUID, payload: ProjectCreate) -> Project:
        """Create a new project owned by the specified user."""
        project = Project(
            owner_id=owner_id,
            name=payload.name,
            description=payload.description,
        )
        self._db.add(project)
        await self._db.flush()
        await self._db.refresh(project)
        return project

    async def get_by_id(
        self, project_id: uuid.UUID, owner_id: uuid.UUID | None = None
    ) -> Project | None:
        """Fetch a single project by ID, optionally verifying owner_id."""
        stmt = select(Project).where(Project.id == project_id)
        if owner_id is not None:
            stmt = stmt.where(Project.owner_id == owner_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Project], int]:
        """Fetch paginated projects owned by the specified user and total count."""
        count_stmt = select(func.count()).select_from(Project).where(Project.owner_id == owner_id)
        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items_result = await self._db.execute(stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def update(self, project: Project, payload: ProjectUpdate) -> Project:
        """Update fields of an existing project."""
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        await self._db.flush()
        await self._db.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        """Delete a project and cascade associated entities."""
        await self._db.delete(project)
        await self._db.flush()
