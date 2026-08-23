"""
Application configuration loaded from environment variables.

Centralises all settings so every module imports from here
instead of calling os.environ directly.
"""

import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Anthropic / LangChain ---
    ANTHROPIC_API_KEY: str = Field(default="")
    LANGCHAIN_TRACING_V2: bool = Field(default=False)
    LANGCHAIN_API_KEY: str = Field(default="")
    LANGCHAIN_PROJECT: str = Field(default="nl-db-platform")

    # --- Platform (metadata) database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://platform:change_me@localhost:5432/platform_db"
    )
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_ECHO: bool = Field(default=False)

    # --- Environment ---
    ENVIRONMENT: str = Field(default="dev")  # "dev" | "staging" | "prod"

    # --- API ---
    API_V1_PREFIX: str = Field(default="/api/v1")

    # --- Vector store ---
    VECTOR_STORE: str = Field(default="pgvector")  # "pgvector" | "chroma"

    # --- Auth ---
    JWT_SECRET_KEY: str = Field(default="change_me_too")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # --- Credential encryption (Fernet) ---
    FERNET_KEY: str = Field(default="")

    # --- CORS ---
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"])


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Use this instead of the module-level ``settings`` singleton when you need
    lazy evaluation (e.g. inside functions that run before the env is loaded).
    """
    return Settings()


# Module-level singleton kept for backward compatibility.
settings = get_settings()
