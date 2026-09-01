"""
SchemaIntrospection domain — SQLAlchemy ORM models.

Contains:
- `SchemaCache`: full introspected raw JSON schema dump per connection.
- `SchemaTable`: normalized table extracted from schema cache.
- `SchemaColumn`: normalized column with data type, PK/FK flags, and ordinal position.
- `SchemaEmbedding`: pgvector embedding per schema column for semantic search.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:
    from app.domain.connections.models import Connection
    from app.domain.semantic_layer.models import SchemaAnnotation


class SchemaCache(TimestampMixin, Base):
    __tablename__ = "schema_cache"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    introspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    connection: Mapped[Connection] = relationship("Connection", back_populates="schema_cache")
    tables: Mapped[list[SchemaTable]] = relationship(
        "SchemaTable", back_populates="cache", cascade="all, delete-orphan"
    )


class SchemaTable(CreatedAtMixin, Base):
    __tablename__ = "schema_tables"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "schema_name",
            "table_name",
            name="uq_schema_tables_conn_schema_table",
        ),
    )

    cache_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_cache.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)

    cache: Mapped[SchemaCache] = relationship("SchemaCache", back_populates="tables")
    columns: Mapped[list[SchemaColumn]] = relationship(
        "SchemaColumn",
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="SchemaColumn.ordinal_position",
    )
    annotations: Mapped[list[SchemaAnnotation]] = relationship(
        "SchemaAnnotation",
        back_populates="table",
        cascade="all, delete-orphan",
        foreign_keys="[SchemaAnnotation.schema_table_id]",
    )


class SchemaColumn(CreatedAtMixin, Base):
    __tablename__ = "schema_columns"
    __table_args__ = (
        Index("ix_schema_columns_conn_table", "connection_id", "table_id"),
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fk_target_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fk_target_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ordinal_position: Mapped[int] = mapped_column(Integer, nullable=False)

    table: Mapped[SchemaTable] = relationship("SchemaTable", back_populates="columns")
    embedding: Mapped[SchemaEmbedding | None] = relationship(
        "SchemaEmbedding",
        back_populates="column",
        uselist=False,
        cascade="all, delete-orphan",
    )
    annotations: Mapped[list[SchemaAnnotation]] = relationship(
        "SchemaAnnotation",
        back_populates="column",
        cascade="all, delete-orphan",
        foreign_keys="[SchemaAnnotation.schema_column_id]",
    )


class SchemaEmbedding(TimestampMixin, Base):
    __tablename__ = "schema_embeddings"

    schema_column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schema_columns.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 768 dimensions for BAAI/bge-base-en-v1.5 / sentence-transformers/all-MiniLM-L6-v2
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    embed_text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        String(100), default="BAAI/bge-base-en-v1.5", nullable=False
    )

    column: Mapped[SchemaColumn] = relationship("SchemaColumn", back_populates="embedding")
