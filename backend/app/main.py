"""
FastAPI application entry point.

Wires together all domain routers and configures middleware,
CORS, lifespan events, and global exception handlers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import app.db  # noqa: F401 - Register all SQLAlchemy models in mapper registry
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.responses import ApiResponse, ErrorDetail
from app.db.session import check_db_connection, connect_with_retry, dispose_engine


class HealthStatus(BaseModel):
    status: str = Field(..., description="Overall health status: 'healthy' or 'degraded'")
    database: str = Field(..., description="Database connectivity: 'connected' or 'disconnected'")
    version: str = Field(default="0.1.0", description="Backend service version")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events."""
    setup_logging()
    # Verify DB connectivity (with retry) before accepting traffic.
    await connect_with_retry()
    yield
    # Gracefully close all pooled DB connections.
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Natural Language Database Querying Platform",
        version="0.1.0",
        description="Multi-tenant agentic NL-to-SQL platform.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom exception handlers for consistent error responses.
    register_exception_handlers(app)

    from app.domain.auth.router import router as auth_router
    from app.domain.connections.router import router as connections_router
    from app.domain.embeddings.router import router as embeddings_router
    from app.domain.projects.router import router as projects_router
    from app.domain.schema_introspection.router import router as schema_router
    from app.domain.semantic_layer.router import router as semantic_router

    app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
    app.include_router(
        projects_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["projects"]
    )
    app.include_router(
        connections_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["connections"]
    )
    app.include_router(
        schema_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["schema"]
    )
    app.include_router(
        semantic_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["semantic_layer"]
    )
    app.include_router(
        embeddings_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["embeddings"]
    )
    # from app.domain.chat.router import router as chat_router
    # app.include_router(chat_router, prefix=f"{settings.API_V1_PREFIX}/chat", tags=["chat"])

    @app.get(
        "/health",
        response_model=ApiResponse[HealthStatus],
        tags=["health"],
        summary="Server and Database Health Check",
    )
    @app.get(
        f"{settings.API_V1_PREFIX}/health",
        response_model=ApiResponse[HealthStatus],
        tags=["health"],
        summary="Server and Database Health Check (v1)",
    )
    async def health_check(response: Response) -> ApiResponse[HealthStatus]:
        """Check if backend server is responsive and platform database is accessible."""
        db_connected = await check_db_connection()
        if not db_connected:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ApiResponse[HealthStatus](
                success=False,
                message="Database connection check failed",
                data=HealthStatus(
                    status="degraded",
                    database="disconnected",
                ),
                error=ErrorDetail(
                    code="SERVICE_UNAVAILABLE",
                    message="Database is unreachable",
                    details=None,
                ),
            )

        return ApiResponse[HealthStatus](
            success=True,
            message="Server and database are healthy",
            data=HealthStatus(
                status="healthy",
                database="connected",
            ),
            error=None,
        )

    return app


app = create_app()
