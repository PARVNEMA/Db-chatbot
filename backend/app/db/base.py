"""SQLAlchemy declarative base and common mixins.

Provides the ``Base`` class that all ORM models inherit from and mixins
that add common columns (``id``, ``created_at``, ``updated_at``) to models.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


class UUIDPrimaryKeyMixin:
    """Mixin that adds standard PostgreSQL UUID primary key ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class CreatedAtMixin(UUIDPrimaryKeyMixin):
    """Mixin that adds ``id`` and ``created_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Mixin that adds ``id``, ``created_at``, and ``updated_at`` columns.

    Inherit from this *before* ``Base``:
        class User(TimestampMixin, Base):
            __tablename__ = "users"
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
