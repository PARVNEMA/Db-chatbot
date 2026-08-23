"""Centralized exception handling.

Defines custom application exceptions and registers FastAPI exception
handlers for consistent error responses across all endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
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
    """

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal server error",
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"ERR_{status_code}"
        self.headers = headers
        super().__init__(detail)


# ── Concrete exceptions ─────────────────────────────────────────────────────


class NotFoundException(AppException):
    """Resource not found (404)."""

    def __init__(self, detail: str = "Resource not found", error_code: str | None = None) -> None:
        super().__init__(status_code=404, detail=detail, error_code=error_code or "NOT_FOUND")


class BadRequestException(AppException):
    """Malformed or invalid request (400)."""

    def __init__(self, detail: str = "Bad request", error_code: str | None = None) -> None:
        super().__init__(status_code=400, detail=detail, error_code=error_code or "BAD_REQUEST")


class UnauthorizedException(AppException):
    """Missing or invalid credentials (401)."""

    def __init__(self, detail: str = "Not authenticated", error_code: str | None = None) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            error_code=error_code or "UNAUTHORIZED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """Insufficient permissions (403)."""

    def __init__(self, detail: str = "Forbidden", error_code: str | None = None) -> None:
        super().__init__(status_code=403, detail=detail, error_code=error_code or "FORBIDDEN")


class ConflictException(AppException):
    """Conflicting state (409) — e.g. duplicate resource."""

    def __init__(self, detail: str = "Conflict", error_code: str | None = None) -> None:
        super().__init__(status_code=409, detail=detail, error_code=error_code or "CONFLICT")


class ValidationException(AppException):
    """Custom validation error (422)."""

    def __init__(self, detail: str = "Validation error", error_code: str | None = None) -> None:
        super().__init__(status_code=422, detail=detail, error_code=error_code or "VALIDATION_ERROR")


# ── Handler registration ────────────────────────────────────────────────────


def _build_error_body(exc: AppException) -> dict[str, Any]:
    """Build a consistent error response body."""
    return {
        "error": {
            "code": exc.error_code,
            "message": exc.detail,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI application.

    Call this once in ``main.py`` after creating the app instance.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(exc),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )