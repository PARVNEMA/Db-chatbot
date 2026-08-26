"""Authentication dependencies for FastAPI.

Provides reusable ``Depends()`` callables for JWT-based authentication
and role-based access control.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import verify_token
from app.db.session import get_db
from app.domain.auth.models import User
from app.domain.auth.repository import UserRepository

settings = get_settings()

http_bearer = HTTPBearer(
    auto_error=True,
    description="Enter JWT access token directly",
)
oauth2_scheme = http_bearer

# Annotated shorthand for injecting the DB session (use in route signatures).
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(http_bearer)],
    db: DbSession,
) -> User:
    """Decode the JWT and return the corresponding ``User``.

    Raises:
        UnauthorizedException: If the token is invalid or the user
            does not exist.
    """
    token = credentials.credentials
    try:
        payload = verify_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise UnauthorizedException(detail="Invalid token: missing subject")
    except JWTError as exc:
        raise UnauthorizedException(detail="Invalid or expired token") from exc

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedException(detail="Invalid token: bad subject format") from exc

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException(detail="User not found")
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current user only if their account is active.

    Raises:
        ForbiddenException: If the user account is deactivated.
    """
    if not current_user.is_active:
        raise ForbiddenException(detail="Inactive user account")
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Return the current user only if they are a superuser.

    Raises:
        ForbiddenException: If the user is not a superuser.
    """
    if not current_user.is_superuser:
        raise ForbiddenException(detail="Superuser access required")
    return current_user
