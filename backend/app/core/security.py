"""
Security utilities: Fernet encryption for connection strings + JWT auth tokens.

Rules:
- Connection strings MUST be encrypted before storing in the platform DB.
- Decryption MUST only happen inside ConnectionManager, never in route handlers.
- Raw keys and decrypted strings MUST NOT be logged.
- JWT tokens are created and verified here; raw secrets MUST NOT be logged.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings


# ── Fernet encryption (connection strings) ────────────────────────────────────


def _get_fernet() -> Fernet:
    if not settings.FERNET_KEY:
        raise RuntimeError("FERNET_KEY is not configured.")
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext connection string. Returns a URL-safe base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to a plaintext connection string.

    Raises:
        ValueError: if the token is malformed or the key is wrong.
    """
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt connection string — invalid token or key.") from exc


# ── JWT authentication ────────────────────────────────────────────────────────


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to embed (must include ``"sub"`` with the user ID).
        expires_delta: Token lifetime; defaults to ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload dict.

    Raises:
        jose.JWTError: If the token is invalid, expired, or the signature
            doesn't match. Callers should catch ``JWTError`` and convert it
            to an ``UnauthorizedException``.
    """
    return jwt.decode(  # type: ignore[return-value]
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
