"""Auth domain — service layer.

Orchestrates authentication workflows, password hashing, and user registration logic.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.core.security import create_access_token, get_password_hash, verify_password
from app.domain.auth.models import User
from app.domain.auth.repository import UserRepository
from app.domain.auth.schemas import UserCreate, UserCreateInternal, UserLogin


class AuthService:
    """Service handling business logic for authentication and user accounts."""

    def __init__(self, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
        self.db = db
        self._repo = UserRepository(db)

    async def register(self, payload: UserCreate) -> User:
        """Register a new user account with hashed password.

        Raises:
            ConflictException: If a user with the specified email already exists.
        """
        existing_user = await self._repo.get_by_email(payload.email)
        if existing_user is not None:
            raise ConflictException(detail="A user with this email address already exists")

        hashed_password = get_password_hash(payload.password)
        user_in = UserCreateInternal(
            email=payload.email,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False,
        )
        return await self._repo.create_user(user_in)

    async def authenticate(self, payload: UserLogin) -> tuple[User, str]:
        """Authenticate user credentials and issue a signed JWT access token.

        Raises:
            UnauthorizedException: If email or password does not match.
            ForbiddenException: If the user account is inactive.
        """
        user = await self._repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedException(detail="Incorrect email or password")

        if not user.is_active:
            raise ForbiddenException(detail="Inactive user account")

        access_token = create_access_token(data={"sub": str(user.id)})
        return user, access_token

    async def logout(self, user: User) -> None:
        """Handle user logout workflow."""
        # For stateless JWTs, client discards token. Hook available for token blacklisting if needed.
        pass


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    """FastAPI dependency provider for AuthService."""
    return AuthService(db)
