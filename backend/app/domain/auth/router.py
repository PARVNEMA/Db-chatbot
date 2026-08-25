"""Auth domain — FastAPI router.

Exposes endpoints for registration, login, logout, and session check/verification.
Mounted under `/api/v1/auth` in `app/main.py`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.responses import ApiResponse, success_response
from app.dependencies.auth import get_current_active_user
from app.domain.auth.models import User
from app.domain.auth.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.domain.auth.services import AuthService, get_auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Create a new user account with a unique email address and password."

)
async def register(
    payload: UserCreate,

    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[UserResponse]:
    """Register a new user account with unique email address."""
    user = await service.register(payload)
    return success_response(
        data=UserResponse.model_validate(user),
        message="User registered successfully",
    )


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT",
)
async def login(
    payload: UserLogin,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    """Authenticate with email and password to receive a JWT access token."""
    user, access_token = await service.authenticate(payload)
    token_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
    return success_response(
        data=token_data,
        message="Login successful",
    )


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Log out the current user session",
)
async def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[None]:
    """Log out the current authenticated user."""
    await service.logout(current_user)
    return success_response(
        data=None,
        message="Successfully logged out",
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[UserResponse]:
    """Return the profile of the currently authenticated active user."""
    return success_response(
        data=UserResponse.model_validate(current_user),
        message="Current user retrieved successfully",
    )


@router.get(
    "/check",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Check authentication status",
)
async def check_auth(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[UserResponse]:
    """Verify validity of current credentials and return active user profile."""
    return success_response(
        data=UserResponse.model_validate(current_user),
        message="Authentication check successful",
    )
