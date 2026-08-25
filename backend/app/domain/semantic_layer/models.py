"""
SemanticLayer domain — SQLAlchemy ORM model.

`SchemaAnnotation` stores user-added notes/annotations for tables and columns
surfaced in the Schema Explorer UI after scanning.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domain.schema_introspection.models import SchemaColumn, SchemaTable


class SchemaAnnotation(TimestampMixin, Base):
    __tablename__ = "schema_annotations"
    __table_args__ = (
        CheckConstraint(
            "(target_type = 'table' AND schema_table_id IS NOT NULL AND schema_column_id IS NULL) OR "
            "(target_type = 'column' AND schema_column_id IS NOT NULL AND schema_table_id IS NULL)",
            name="ck_schema_annotations_target_type",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_tables.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    schema_column_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_columns.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "table" | "column"
    note: Mapped[str] = mapped_column(Text, nullable=False)

    table: Mapped[SchemaTable | None] = relationship(
        "SchemaTable",
        back_populates="annotations",
        foreign_keys=[schema_table_id],
    )
    column: Mapped[SchemaColumn | None] = relationship(
        "SchemaColumn",
        back_populates="annotations",
        foreign_keys=[schema_column_id],
    )
