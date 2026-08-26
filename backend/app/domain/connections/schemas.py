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


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    dialect: str
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
