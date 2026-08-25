"""
Projects domain — SQLAlchemy ORM model.

`Project` is the root multi-tenant isolation boundary, owned by a `User`.
Every other entity (Connection, SchemaCache, SchemaAnnotations, ChatSession)
carries a foreign-key reference to `Project.id`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domain.auth.models import User
    from app.domain.chat.models import ChatSession
    from app.domain.connections.models import Connection


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    owner: Mapped[User] = relationship("User", back_populates="projects")
    connection: Mapped[Connection | None] = relationship(
        "Connection", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="project", cascade="all, delete-orphan"
    )
