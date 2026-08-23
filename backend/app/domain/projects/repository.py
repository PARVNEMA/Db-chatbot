"""
Projects domain — repository layer.

All database access for `Project` rows is centralised here.
Every method is scoped by project_id where applicable.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.projects.models import Project
from app.domain.projects.schemas import ProjectCreate, ProjectUpdate


class ProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, payload: ProjectCreate) -> Project:
        project = Project(**payload.model_dump())
        self._db.add(project)
        await self._db.flush()
        await self._db.refresh(project)
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        result = await self._db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Project]:
        result = await self._db.execute(select(Project).order_by(Project.created_at.desc()))
        return list(result.scalars().all())

    async def update(self, project: Project, payload: ProjectUpdate) -> Project:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        await self._db.flush()
        await self._db.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self._db.delete(project)
        await self._db.flush()
