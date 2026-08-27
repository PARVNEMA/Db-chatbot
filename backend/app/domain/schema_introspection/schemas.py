"""
SchemaIntrospection domain — Pydantic v2 schemas.

Defines response models for introspected tables, columns,
schema overviews, and live introspection execution results.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ColumnResponse(BaseModel):
    """Pydantic model representing a database column in the schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    table_id: uuid.UUID
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    fk_target_table: str | None = None
    fk_target_column: str | None = None
    ordinal_position: int
    created_at: datetime


class TableResponse(BaseModel):
    """Pydantic model representing a table summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    project_id: uuid.UUID
    schema_name: str | None = None
    table_name: str
    column_count: int = 0
    created_at: datetime


class TableDetailResponse(BaseModel):
    """Pydantic model representing a table with full column details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    project_id: uuid.UUID
    schema_name: str | None = None
    table_name: str
    columns: list[ColumnResponse] = Field(default_factory=list)
    created_at: datetime


class SchemaOverviewResponse(BaseModel):
    """High-level summary of introspected schema metadata."""

    model_config = ConfigDict(from_attributes=True)

    connection_id: uuid.UUID
    project_id: uuid.UUID
    introspected_at: datetime
    table_count: int
    tables: list[TableResponse] = Field(default_factory=list)


class IntrospectResponse(BaseModel):
    """Detailed response returned immediately after running introspection."""

    model_config = ConfigDict(from_attributes=True)

    connection_id: uuid.UUID
    project_id: uuid.UUID
    introspected_at: datetime
    table_count: int
    column_count: int
    tables: list[TableDetailResponse] = Field(default_factory=list)

