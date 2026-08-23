"""
SchemaIntrospection domain — SQLAlchemy ORM model.

`SchemaCache` stores the introspected structure of a target database
(tables, columns, PKs/FKs) as structured JSON, keyed to a `Connection`
and scoped to a `Project`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SchemaCache(Base):
    __tablename__ = "schema_caches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Introspected schema stored as:
    # {"tables": [{"name": str, "columns": [...], "primary_keys": [...], "foreign_keys": [...]}]}
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    introspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
