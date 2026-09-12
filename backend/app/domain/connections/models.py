"""
Connections domain — SQLAlchemy ORM model.

`Connection` stores encrypted credentials and dialect info for
a user-supplied target database, scoped strictly to one `Project` (1:1).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domain.chat.models import ChatSession
    from app.domain.projects.models import Project
    from app.domain.schema_introspection.models import SchemaCache


class Connection(TimestampMixin, Base):
    __tablename__ = "connections"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dialect: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g. "postgresql", "mysql", "mssql", "snowflake"
    # Encrypted via Fernet before insert; decrypted ONLY inside ConnectionManager
    encrypted_connection_string: Mapped[str] = mapped_column(String(2048), nullable=False)

    # Write policy & safety limits
    writes_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_insert_rows_per_table: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_patch_rows_per_table: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_total_rows_per_changeset: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_tables_per_changeset: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approval_timeout_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    undo_window_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_tables: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="connection")
    schema_cache: Mapped[SchemaCache | None] = relationship(
        "SchemaCache", back_populates="connection", uselist=False, cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession", back_populates="connection", cascade="all, delete-orphan"
    )
