"""
FastAPI application entry point.

Wires together all domain routers and configures middleware,
CORS, lifespan events, and global exception handlers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import connect_with_retry, dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown events."""
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

    # Domain routers registered here as they are implemented
    # from app.domain.projects.router import router as projects_router
    # from app.domain.connections.router import router as connections_router
    # from app.domain.schema_introspection.router import router as schema_router
    # from app.domain.semantic_layer.router import router as semantic_router
    # from app.domain.chat.router import router as chat_router
    # app.include_router(projects_router, prefix=f"{settings.API_V1_PREFIX}/projects", tags=["projects"])
    # app.include_router(connections_router, prefix=f"{settings.API_V1_PREFIX}/connections", tags=["connections"])
    # app.include_router(schema_router, prefix=f"{settings.API_V1_PREFIX}/schema", tags=["schema"])
    # app.include_router(semantic_router, prefix=f"{settings.API_V1_PREFIX}/semantic", tags=["semantic"])
    # app.include_router(chat_router, prefix=f"{settings.API_V1_PREFIX}/chat", tags=["chat"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
