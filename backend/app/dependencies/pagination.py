"""Pagination dependencies for FastAPI.

Provides reusable pagination query parameters for list endpoints.
"""

from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Reusable query parameter model for limit/offset pagination."""

    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of records to return")


Pagination = Annotated[PaginationParams, Depends()]
