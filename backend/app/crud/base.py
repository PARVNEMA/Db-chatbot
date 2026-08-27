"""Generic async CRUD base class.

Provides reusable Create / Read / Update / Delete operations using
SQLAlchemy 2.0 ``select()`` style and ``AsyncSession``.

Usage::

    from app.crud.base import CRUDBase
    from app.db.base import Base, TimestampMixin
    from app.schemas.item import ItemCreate, ItemUpdate

    class Item(TimestampMixin, Base):
        __tablename__ = "items"
        ...

    class CRUDItem(CRUDBase[Item, ItemCreate, ItemUpdate]):
        pass

    crud_item = CRUDItem(Item)
"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic CRUD operations for a SQLAlchemy model.

    Args:
        model: The SQLAlchemy model class to operate on.
    """

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> ModelType | None:
        """Fetch a single record by primary key.

        Args:
            db: Async database session.
            id: Primary key UUID.

        Returns:
            The model instance, or ``None`` if not found.
        """
        stmt = select(self.model).where(self.model.id == id)  # type: ignore[union-attr]
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[ModelType]:
        """Fetch multiple records with offset/limit pagination.

        Args:
            db: Async database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of model instances.
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
    ) -> ModelType:
        """Insert a new record.

        Args:
            db: Async database session.
            obj_in: Pydantic schema with creation data.

        Returns:
            The newly created model instance.
        """
        obj_data = obj_in.model_dump()
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """Update an existing record.

        Only fields present in *obj_in* (with non-``None`` values when using
        ``exclude_unset``) are written to the database.

        Args:
            db: Async database session.
            db_obj: Existing model instance to update.
            obj_in: Pydantic schema or dict with update data.

        Returns:
            The updated model instance.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: UUID) -> ModelType | None:
        """Delete a record by primary key.

        Args:
            db: Async database session.
            id: Primary key UUID of the record to delete.

        Returns:
            The deleted model instance, or ``None`` if not found.
        """
        db_obj = await self.get(db, id)
        if db_obj is None:
            return None
        await db.delete(db_obj)
        await db.commit()
        return db_obj

    async def count(self, db: AsyncSession) -> int:
        """Return the total number of records.

        Args:
            db: Async database session.

        Returns:
            Row count.
        """
        stmt = select(func.count()).select_from(self.model)
        result = await db.execute(stmt)
        return result.scalar_one()
