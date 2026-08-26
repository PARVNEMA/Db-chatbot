"""
Projects domain — Pydantic v2 request/response schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project display name")
    description: str | None = Field(
        default=None, max_length=1024, description="Optional project description"
    )


class ProjectUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Project display name"
    )
    description: str | None = Field(
        default=None, max_length=1024, description="Optional project description"
    )


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
