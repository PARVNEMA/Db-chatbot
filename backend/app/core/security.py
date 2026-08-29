"""
Security utilities: Fernet encryption for connection strings + JWT auth tokens.

Rules:
- Connection strings MUST be encrypted before storing in the platform DB.
- Decryption MUST only happen inside ConnectionManager, never in route handlers.
- Raw keys and decrypted strings MUST NOT be logged.
- JWT tokens are created and verified here; raw secrets MUST NOT be logged.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import jwt

from app.core.config import get_settings, settings

# ── Fernet encryption (connection strings) ────────────────────────────────────

_PLAIN_URI_PREFIXES: tuple[str, ...] = (
    "postgresql://",
    "postgresql+asyncpg://",
    "postgresql+psycopg2://",
    "postgresql+psycopg://",
    "sqlite://",
    "sqlite+aiosqlite://",
    "mysql://",
    "mysql+asyncmy://",
    "mysql+pymysql://",
    "mssql://",
    "oracle://",
    "cockroachdb://",
    "snowflake://",
)


def _derive_fernet_key(key_material: str) -> bytes:
    """Derive a 32-byte URL-safe base64 Fernet key from any string or validate existing."""
    try:
        decoded = base64.urlsafe_b64decode(key_material.encode("utf-8"))
        if len(decoded) == 32:
            return key_material.encode("utf-8")
    except Exception:
        pass
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    current_settings = get_settings()
    if not current_settings.FERNET_KEY:
        raise RuntimeError("FERNET_KEY is not configured.")
    return Fernet(_derive_fernet_key(current_settings.FERNET_KEY))


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext connection string. Returns a URL-safe base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to a plaintext connection string.

    If the string is already a plaintext database URI (e.g. from local testing or dev seeds),
    it is returned directly.

    Raises:
        ValueError: if the token is malformed or the key is wrong.
    """
    if not token:
        raise ValueError("Connection string token is empty.")

    # Check if already a plaintext database connection URI
    lowered = token.lower().strip()
    if any(lowered.startswith(prefix) for prefix in _PLAIN_URI_PREFIXES):
        return token.strip()

    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt connection string. This occurs if the FERNET_KEY was changed "
            "after saving the connection, or if the stored credentials are invalid. "
            "Please update/re-save the database connection under project settings."
        ) from exc


# Aliases adhering to AGENTS.md naming conventions
encrypt_secret = encrypt
decrypt_secret = decrypt


# ── Password hashing ─────────────────────────────────────────────────────────


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an existing bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


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
    expire = datetime.now(tz=UTC) + (
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
