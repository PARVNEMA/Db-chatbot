"""SQLAlchemy declarative base and common mixins.

Provides the ``Base`` class that all ORM models inherit from and a
``TimestampMixin`` that adds ``id``, ``created_at``, and ``updated_at``
columns to any model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


class TimestampMixin:
    """Mixin that adds ``id``, ``created_at``, and ``updated_at`` columns.

    Inherit from this *before* ``Base`` so the columns appear first in
    the table definition::

        class User(TimestampMixin, Base):
            __tablename__ = "users"
            ...
    """

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )