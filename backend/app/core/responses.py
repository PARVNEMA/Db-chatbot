"""Standardized API response wrappers and schemas.

Provides a unified envelope for both success and error responses
across all FastAPI endpoints:

    {
        "success": true,
        "message": "Operation completed successfully",
        "data": { ... },
        "error": null
    }

and for error responses:

    {
        "success": false,
        "message": "Resource not found",
        "data": null,
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
            "details": null
        }
    }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error payload within an API response."""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable error description")
    details: Any | None = Field(
        default=None, description="Optional granular validation or error context"
    )


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response envelope for all endpoints."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(default=True, description="Indicates if the request was successful")
    message: str = Field(
        default="Operation completed successfully", description="Human-readable status message"
    )
    data: T | None = Field(default=None, description="Response payload for successful operations")
    error: ErrorDetail | None = Field(
        default=None, description="Error detail if the operation failed"
    )


class PaginatedData(BaseModel, Generic[T]):
    """Standard container for paginated list results."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T] = Field(
        default_factory=list, description="List of records for the current page"
    )
    total: int = Field(..., description="Total count of available records")
    skip: int = Field(0, description="Offset used in query")
    limit: int = Field(20, description="Page limit used in query")


def success_response(
    data: Any = None,
    message: str = "Operation completed successfully",
) -> dict[str, Any]:
    """Helper to construct a success response dictionary."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "error": None,
    }


def error_response(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Helper to construct an error response dictionary."""
    return {
        "success": False,
        "message": message,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def paginated_response(
    items: list[Any],
    total: int,
    skip: int = 0,
    limit: int = 20,
    message: str = "Records retrieved successfully",
) -> dict[str, Any]:
    """Helper to construct a standardized paginated ApiResponse dictionary.

    The paginated payload (`items`, `total`, `skip`, `limit`) is wrapped
    strictly inside the `data` field of the `ApiResponse`.
    """
    return success_response(
        data={
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
        },
        message=message,
    )

