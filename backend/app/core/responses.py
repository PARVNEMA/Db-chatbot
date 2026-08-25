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
    data: T | None = None,
    message: str = "Operation completed successfully",
) -> ApiResponse[T]:
    """Helper to construct a standardized success ApiResponse model."""
    return ApiResponse[T](
        success=True,
        message=message,
        data=data,
        error=None,
    )


def error_response(
    code: str,
    message: str,
    details: Any | None = None,
) -> ApiResponse[None]:
    """Helper to construct a standardized error ApiResponse model."""
    return ApiResponse[None](
        success=False,
        message=message,
        data=None,
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
        ),
    )


def paginated_response(
    items: list[T],
    total: int,
    skip: int = 0,
    limit: int = 20,
    message: str = "Records retrieved successfully",
) -> ApiResponse[PaginatedData[T]]:
    """Helper to construct a standardized paginated ApiResponse model.

    The paginated payload (`items`, `total`, `skip`, `limit`) is wrapped
    strictly inside the `data` field of the `ApiResponse`.
    """
    return ApiResponse[PaginatedData[T]](
        success=True,
        message=message,
        data=PaginatedData[T](
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        ),
        error=None,
    )

