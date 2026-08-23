"""
Connections domain — Pydantic v2 request/response schemas.

NOTE: The raw connection string is accepted on create/test but is NEVER
returned in any response; only encrypted tokens are stored.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    dialect: str = Field(..., examples=["postgresql", "mysql", "mssql", "snowflake"])
    connection_string: str = Field(..., min_length=1, description="Plaintext; encrypted before storage.")


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    connection_string: str | None = Field(default=None, min_length=1)


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    dialect: str
    # Raw connection string is intentionally excluded
    created_at: datetime
    updated_at: datetime
