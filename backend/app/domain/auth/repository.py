"""Auth domain — repository layer.

Data access layer for User entities using CRUDBase and SQLAlchemy 2.0.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.domain.auth.models import User
from app.domain.auth.schemas import UserCreateInternal, UserUpdate


class UserRepository(CRUDBase[User, UserCreateInternal, UserUpdate]):
    """Repository handling all database operations for User records."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User)
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user record by primary key UUID."""
        return await self.get(self.db, id=user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user record by email address (case-insensitive)."""
        stmt = select(User).where(User.email == email.lower().strip())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_user(self, obj_in: UserCreateInternal) -> User:
        """Insert a new user record into the database."""
        return await self.create(self.db, obj_in=obj_in)

    async def update_user(
        self,
        user: User,
        obj_in: UserUpdate | dict[str, Any],
    ) -> User:
        """Update an existing user record."""
        return await self.update(self.db, db_obj=user, obj_in=obj_in)
