"""
Connections domain — Pydantic v2 request/response schemas.

NOTE: The raw connection string is accepted on create/test but is NEVER
returned in any response; only encrypted credentials are saved.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Connection display name")
    dialect: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Database dialect (e.g. postgresql, mysql, sqlite, snowflake)",
        examples=["postgresql", "mysql", "sqlite"],
    )
    connection_string: str = Field(
        ...,
        min_length=1,
        description="Plaintext target connection string; encrypted before storage.",
    )


class WritePolicyUpdate(BaseModel):
    writes_enabled: bool | None = Field(default=None, description="Toggle write capability for the connection")
    max_insert_rows_per_table: int | None = Field(
        default=None, ge=1, le=50, description="Max rows per INSERT per table"
    )
    max_patch_rows_per_table: int | None = Field(
        default=None, ge=1, le=20, description="Max rows per PATCH per table"
    )
    max_total_rows_per_changeset: int | None = Field(
        default=None, ge=1, le=100, description="Max total rows affected per change-set"
    )
    max_tables_per_changeset: int | None = Field(
        default=None, ge=1, le=5, description="Max distinct tables modified per change-set"
    )
    approval_timeout_minutes: int | None = Field(
        default=None, ge=1, le=120, description="Approval expiry timeout in minutes"
    )
    undo_window_minutes: int | None = Field(
        default=None, ge=0, le=1440, description="Window in minutes during which soft-undo is available"
    )
    blocked_tables: list[str] | None = Field(
        default=None, description="Denylist of tables that cannot be modified"
    )


class ConnectionUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Connection display name"
    )
    dialect: str | None = Field(
        default=None, min_length=1, max_length=50, description="Database dialect"
    )
    connection_string: str | None = Field(
        default=None, min_length=1, description="New plaintext connection string"
    )
    writes_enabled: bool | None = None
    max_insert_rows_per_table: int | None = Field(default=None, ge=1, le=50)
    max_patch_rows_per_table: int | None = Field(default=None, ge=1, le=20)
    max_total_rows_per_changeset: int | None = Field(default=None, ge=1, le=100)
    max_tables_per_changeset: int | None = Field(default=None, ge=1, le=5)
    approval_timeout_minutes: int | None = Field(default=None, ge=1, le=120)
    undo_window_minutes: int | None = Field(default=None, ge=0, le=1440)
    blocked_tables: list[str] | None = None


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    dialect: str
    writes_enabled: bool = False
    max_insert_rows_per_table: int = 5
    max_patch_rows_per_table: int = 1
    max_total_rows_per_changeset: int = 10
    max_tables_per_changeset: int = 1
    approval_timeout_minutes: int = 15
    undo_window_minutes: int = 0
    blocked_tables: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionTestRequest(BaseModel):
    connection_string: str = Field(
        ..., min_length=1, description="Target database connection URL to test"
    )
    dialect: str | None = Field(default=None, description="Optional dialect hint")


class ConnectionTestResponse(BaseModel):
    success: bool = Field(..., description="True if connection succeeded")
    latency_ms: float | None = Field(
        default=None, description="Connection handshake roundtrip latency in milliseconds"
    )
    dialect: str | None = Field(default=None, description="Detected or verified dialect")
    message: str = Field(..., description="Human-readable connection test outcome")
