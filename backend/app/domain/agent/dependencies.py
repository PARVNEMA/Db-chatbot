"""
Agent domain — Graph dependencies container (ADR-0003).

Provides runtime dependency injection for LangGraph execution nodes,
including database access, connection management, embedding search,
and configured LLM instances.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import get_llm_client
from app.domain.connections.manager import ConnectionManager, connection_manager
from app.domain.connections.models import Connection
from app.domain.connections.services import ConnectionService
from app.domain.embeddings.services import EmbeddingService
from app.domain.projects.services import ProjectService
from app.domain.schema_introspection.services import SchemaIntrospectionService


@dataclass(frozen=True)
class GraphDependencies:
    """Runtime dependencies injected into LangGraph pipeline nodes."""

    db: AsyncSession
    connection_manager: ConnectionManager
    embedding_service: EmbeddingService
    connection_service: ConnectionService
    project_service: ProjectService
    connection: Connection
    llm: BaseChatModel
    user_id: uuid.UUID
    schema_service: SchemaIntrospectionService | None = None


async def build_graph_dependencies(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    manager: ConnectionManager = connection_manager,
    llm_override: BaseChatModel | None = None,
) -> GraphDependencies:
    """Build and resolve runtime dependencies for executing the agent graph.

    Args:
        db: Active async database session for the platform DB.
        project_id: The tenant project UUID.
        user_id: The authenticated user UUID (for permission checks).
        manager: Connection manager instance.
        llm_override: Optional LLM instance override (e.g. for testing).

    Returns:
        GraphDependencies container with all resolved domain services and target connection.
    """
    project_service = ProjectService(db=db)
    connection_service = ConnectionService(
        db=db,
        project_service=project_service,
        manager=manager,
    )
    # Fetch connection and verify ownership
    connection = await connection_service.get_connection(
        project_id=project_id,
        user_id=user_id,
    )
    embedding_service = EmbeddingService(
        db=db,
        connection_service=connection_service,
    )
    schema_service = SchemaIntrospectionService(
        db=db,
        connection_service=connection_service,
        manager=manager,
    )
    llm = llm_override or get_llm_client()

    return GraphDependencies(
        db=db,
        connection_manager=manager,
        embedding_service=embedding_service,
        connection_service=connection_service,
        project_service=project_service,
        connection=connection,
        llm=llm,
        user_id=user_id,
        schema_service=schema_service,
    )
