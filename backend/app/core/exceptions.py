"""Centralized exception handling.

Defines custom application exceptions and registers FastAPI exception
handlers for consistent error responses across all endpoints.
"""

from __future__ import annotations

import logging
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


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI application.

    Call this once in ``main.py`` after creating the app instance.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
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
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_build_error_body(
                message="Request validation failed",
                code="VALIDATION_ERROR",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_build_error_body(
                message="An unexpected error occurred",
                code="INTERNAL_SERVER_ERROR",
                details=None,
            ),
        )