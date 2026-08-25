"""app.core package — foundational platform components and utilities."""

from app.core.config import get_settings, settings
from app.core.exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
    register_exception_handlers,
)
from app.core.responses import (
    ApiResponse,
    ErrorDetail,
    PaginatedData,
    error_response,
    paginated_response,
    success_response,
)

__all__ = [
    "settings",
    "get_settings",
    "ApiResponse",
    "PaginatedData",
    "ErrorDetail",
    "success_response",
    "paginated_response",
    "error_response",
    "AppException",
    "NotFoundException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "ConflictException",
    "ValidationException",
    "register_exception_handlers",
]
