"""Auth domain — Pydantic schemas.

Request validation, response serialization, and domain DTOs for authentication.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared properties for User models."""

    email: EmailStr = Field(..., description="User's unique email address")
    is_active: bool = Field(default=True, description="Whether the user account is active")
    is_superuser: bool = Field(default=False, description="Whether the user has superuser privileges")


class UserCreate(BaseModel):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User's unique email address", examples=["user1@example.com"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=12,
        description="Plaintext password (min 8 characters)",
        examples=["password123"]
    )


class UserCreateInternal(BaseModel):
    """Internal schema for creating a user record in the database."""

    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    """Schema for updating a user record."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    is_superuser: bool | None = None


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="User's email address", examples=['user1@example.com'])
    password: str = Field(..., description="User's plaintext password",examples=['password123'])


class UserResponse(BaseModel):
    """Public user response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User's email address")
    is_active: bool = Field(..., description="Active status")
    is_superuser: bool = Field(..., description="Superuser status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Account last updated timestamp")


class TokenResponse(BaseModel):
    """Response returned upon successful authentication."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="Authenticated user profile")
