"""
Chat domain — Service layer (Phase 9).

Orchestrates ChatSession CRUD, multi-turn message management, LangGraph agent execution,
and Server-Sent Event (SSE) streaming of agent progress and execution results.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies.auth import DbSession
from app.dependencies.pagination import PaginationParams
from app.domain.agent.dependencies import build_graph_dependencies
from app.domain.agent.graph import build_agent_graph
from app.domain.agent.state import AgentState
from app.domain.chat.models import ChatMessage, ChatSession
from app.domain.chat.repository import (
    ChatMessageRepository,
    ChatSessionRepository,
    QueryRunRepository,
)
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.projects.services import ProjectService, get_project_service

logger = logging.getLogger(__name__)


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """Format an SSE message block with event name and JSON payload."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _build_history_messages(recent_messages: list[ChatMessage]) -> list[BaseMessage]:
    """Convert stored chat messages to LangChain message models."""
    history: list[BaseMessage] = []
    for m in recent_messages[:-1]:  # Exclude current user message
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history.append(AIMessage(content=m.content))
    return history


def _format_node_event(node_name: str, node_output: dict[str, Any]) -> str | None:
    """Format SSE event string for a specific node update in the graph."""
    if node_name == "intent":
        return _format_sse(
            "intent_classified",
            {
                "intent_type": node_output.get("intent_type"),
                "extracted_entities": node_output.get("extracted_entities"),
            },
        )
    if node_name == "sql_generator":
        return _format_sse(
            "sql_generated",
            {
                "generated_sql": node_output.get("generated_sql"),
                "sql_dialect": node_output.get("sql_dialect"),
            },
        )
    if node_name == "sql_executor":
        err = node_output.get("execution_error")
        if err:
            return _format_sse(
                "sql_error",
                {
                    "error": err,
                    "retry_count": node_output.get("retry_count", 1),
                },
            )
        rows = node_output.get("execution_result", [])
        return _format_sse(
            "sql_executed",
            {
                "row_count": len(rows),
                "sample_rows": rows[:10],
            },
        )
    if node_name in {"result_formatter", "error_terminal", "general_chat", "unsafe_handler"}:
        return _format_sse(
            "summary_ready",
            {
                "nl_summary": node_output.get("nl_summary"),
            },
        )
    return None


class ChatService:
    """Domain service managing chat sessions, messages, and agent execution."""

    def __init__(
        self,
        db: AsyncSession,
        project_service: ProjectService,
        connection_service: ConnectionService,
    ) -> None:
        self._db = db
        self._project_service = project_service
        self._connection_service = connection_service
        self._session_repo = ChatSessionRepository(db)
        self._message_repo = ChatMessageRepository(db)
        self._query_run_repo = QueryRunRepository(db)

    async def create_session(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatSession:
        """Create a new chat session bound to the project's database connection."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        connection = await self._connection_service.get_connection(
            project_id=project_id,
            user_id=user_id,
        )
        return await self._session_repo.create_session(
            project_id=project_id,
            connection_id=connection.id,
            title=title or "New Query Session",
        )

    async def list_sessions(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> tuple[list[ChatSession], int]:
        """List chat sessions for a project with total count."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        return await self._session_repo.list_by_project(
            project_id=project_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

    async def get_session(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChatSession:
        """Retrieve a chat session ensuring project ownership."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        session = await self._session_repo.get_by_id_and_project(
            session_id=session_id,
            project_id=project_id,
        )
        if session is None:
            raise NotFoundException(
                detail=f"Chat session '{session_id}' not found.",
                error_code="CHAT_SESSION_NOT_FOUND",
            )
        return session

    async def update_session_title(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None,
    ) -> ChatSession:
        """Update session title."""
        session = await self.get_session(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
        )
        return await self._session_repo.update_title(session=session, title=title)

    async def delete_session(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a chat session and associated messages."""
        session = await self.get_session(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
        )
        await self._session_repo.delete_session(session=session)

    async def list_messages(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> tuple[list[ChatMessage], int]:
        """List messages for a chat session."""
        await self.get_session(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
        )
        return await self._message_repo.list_by_session(
            session_id=session_id,
            project_id=project_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

    async def send_message_stream(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
    ) -> AsyncGenerator[str, None]:
        """Process a user question through the LangGraph agent pipeline and stream SSE updates."""
        start_time = time.perf_counter()

        # 1. Validate session and access
        session = await self.get_session(
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
        )

        # 2. Persist user message
        user_msg = await self._message_repo.create_message(
            session_id=session_id,
            project_id=project_id,
            role="user",
            content=content,
        )

        yield _format_sse(
            "message_received",
            {
                "message_id": str(user_msg.id),
                "role": "user",
                "content": content,
            },
        )

        # 3. Build graph dependencies
        try:
            deps = await build_graph_dependencies(
                db=self._db,
                project_id=project_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.error("Failed to build graph dependencies: %s", exc)
            yield _format_sse("error", {"message": f"Initialization failed: {exc}"})
            yield _format_sse("done", {})
            return

        # 4. Fetch recent messages for multi-turn conversational context
        recent_messages = await self._message_repo.get_recent_messages(
            session_id=session_id,
            project_id=project_id,
            limit=10,
        )
        history = _build_history_messages(recent_messages)

        # 5. Compile LangGraph agent workflow
        graph = build_agent_graph(deps=deps)

        initial_state: AgentState = {
            "project_id": project_id,
            "session_id": session_id,
            "connection_id": session.connection_id,
            "user_query": content,
            "intent_type": "general",
            "extracted_entities": [],
            "relevant_schema": {},
            "schema_context": "",
            "generated_sql": "",
            "sql_dialect": deps.connection.dialect,
            "execution_result": [],
            "execution_error": None,
            "retry_count": 0,
            "error_history": [],
            "nl_summary": "",
            "messages": history,
        }

        # 6. Stream graph execution step-by-step
        final_state: dict[str, Any] = dict(initial_state)

        try:
            async for update in graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in update.items():
                    if not isinstance(node_output, dict):
                        continue
                    final_state.update(node_output)
                    event_chunk = _format_node_event(node_name, node_output)
                    if event_chunk:
                        yield event_chunk

        except Exception as graph_err:
            logger.exception("LangGraph execution error: %s", graph_err)
            final_state["execution_error"] = str(graph_err)
            final_state["nl_summary"] = f"An unexpected error occurred during execution: {graph_err}"
            yield _format_sse("error", {"message": str(graph_err)})

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        execution_status = "success" if final_state.get("execution_error") is None else "failed"

        # 7. Persist assistant message and query run record
        query_run = await self._query_run_repo.create_query_run(
            chat_message_id=user_msg.id,
            project_id=project_id,
            connection_id=session.connection_id,
            nl_prompt=content,
            generated_sql=final_state.get("generated_sql"),
            status=execution_status,
            error_message=final_state.get("execution_error"),
            result_summary=final_state.get("nl_summary"),
            result_row_count=len(final_state.get("execution_result", [])),
            latency_ms=latency_ms,
            attempt_number=max(1, final_state.get("retry_count", 0)),
        )

        assistant_msg = await self._message_repo.create_message(
            session_id=session_id,
            project_id=project_id,
            role="assistant",
            content=final_state.get("nl_summary", "Query completed."),
            query_run_id=query_run.id,
            metadata_json={
                "sql": final_state.get("generated_sql"),
                "dialect": final_state.get("sql_dialect"),
                "status": execution_status,
                "latency_ms": latency_ms,
                "row_count": len(final_state.get("execution_result", [])),
            },
        )

        # 8. Emit final result
        yield _format_sse(
            "final_result",
            {
                "assistant_message_id": str(assistant_msg.id),
                "query_run_id": str(query_run.id),
                "content": assistant_msg.content,
                "generated_sql": final_state.get("generated_sql"),
                "execution_result": final_state.get("execution_result", []),
                "status": execution_status,
                "latency_ms": latency_ms,
            },
        )

        yield _format_sse("done", {})


def get_chat_service(
    db: DbSession,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> ChatService:
    """FastAPI dependency provider for ChatService."""
    return ChatService(
        db=db,
        project_service=project_service,
        connection_service=connection_service,
    )
