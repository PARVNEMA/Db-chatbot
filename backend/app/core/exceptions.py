"""Centralized exception handling.

Defines custom application exceptions and registers FastAPI exception
handlers for consistent error responses across all endpoints.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Base exception ───────────────────────────────────────────────────────────


class AppException(Exception):
    """Base application exception.

    All custom exceptions inherit from this so they can be caught by
    a single handler.

    Attributes:
        status_code: HTTP status code to return.
        detail: Human-readable error message.
        error_code: Machine-readable error identifier.
        details: Optional granular validation or context details.
        headers: Optional response HTTP headers.
    """

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal server error",
        error_code: str | None = None,
        details: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"ERR_{status_code}"
        self.details = details
        self.headers = headers
        super().__init__(detail)


# ── Concrete exceptions ─────────────────────────────────────────────────────


class NotFoundException(AppException):
    """Resource not found (404)."""

    def __init__(
        self,
        detail: str = "Resource not found",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=404,
            detail=detail,
            error_code=error_code or "NOT_FOUND",
            details=details,
        )


class BadRequestException(AppException):
    """Malformed or invalid request (400)."""

    def __init__(
        self,
        detail: str = "Bad request",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=error_code or "BAD_REQUEST",
            details=details,
        )


class UnauthorizedException(AppException):
    """Missing or invalid credentials (401)."""

    def __init__(
        self,
        detail: str = "Not authenticated",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=error_code or "UNAUTHORIZED",
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """Insufficient permissions (403)."""

    def __init__(
        self,
        detail: str = "Forbidden",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=403,
            detail=detail,
            error_code=error_code or "FORBIDDEN",
            details=details,
        )


class ConflictException(AppException):
    """Conflicting state (409) — e.g. duplicate resource."""

    def __init__(
        self,
        detail: str = "Conflict",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=409,
            detail=detail,
            error_code=error_code or "CONFLICT",
            details=details,
        )


class ValidationException(AppException):
    """Custom validation error (422)."""

    def __init__(
        self,
        detail: str = "Validation error",
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=422,
            detail=detail,
            error_code=error_code or "VALIDATION_ERROR",
            details=details,
        )


# ── Handler registration ────────────────────────────────────────────────────


def _build_error_body(
    message: str,
    code: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build a consistent error response body conforming to ApiResponse envelope."""
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


def _format_validation_errors(errors: Sequence[Any]) -> list[dict[str, str]]:
    """Convert raw Pydantic/FastAPI validation errors into clean, concise dictionaries."""
    formatted: list[dict[str, str]] = []
    for err in errors:
        if isinstance(err, dict):
            loc_parts = [str(item) for item in err.get("loc", []) if item != "body"]
            msg = err.get("msg", "Invalid value")
        else:
            loc_parts = [str(item) for item in getattr(err, "loc", []) if item != "body"]
            msg = getattr(err, "msg", "Invalid value")
        field_name = " -> ".join(loc_parts) if loc_parts else "body"
        msg = err.get("msg", "Invalid value")
        formatted.append({
            "field": field_name,
            "message": msg,
        })
    return formatted


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI application.

    Call this once in ``main.py`` after creating the app instance.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "[%s] %s %s -> %s",
            exc.error_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(
                message=exc.detail,
                code=exc.error_code,
                details=exc.details,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        clean_errors = _format_validation_errors(exc.errors())
        error_summary = "; ".join(f"{e['field']}: {e['message']}" for e in clean_errors)
        logger.warning(
            "[VALIDATION_ERROR] %s %s -> %s",
            request.method,
            request.url.path,
            error_summary or "Request validation failed",
        )
        return JSONResponse(
            status_code=422,
            content=_build_error_body(
                message=f"Validation failed: {error_summary}" if error_summary else "Request validation failed",
                code="VALIDATION_ERROR",
                details=clean_errors,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "[INTERNAL_ERROR] %s %s -> %s: %s",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=_build_error_body(
                message="An unexpected error occurred",
                code="INTERNAL_SERVER_ERROR",
                details=None,
            ),
        )
