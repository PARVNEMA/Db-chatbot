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
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.security import decrypt_secret, encrypt_secret
from app.core.websocket import WebSocketConnectionManager, websocket_manager
from app.dependencies.auth import DbSession
from app.dependencies.pagination import PaginationParams
from app.domain.agent.dependencies import build_graph_dependencies
from app.domain.agent.graph import build_agent_graph
from app.domain.agent.nodes.mutation_executor import (
    execute_change_set,
    execute_undo_change_set,
)
from app.domain.agent.nodes.mutation_previewer import compute_change_set_hash
from app.domain.agent.state import AgentState
from app.domain.chat.models import ChatMessage, ChatSession, MutationAuditLog, PendingMutation
from app.domain.chat.rate_limiter import mutation_rate_limiter
from app.domain.chat.repository import (
    ChatMessageRepository,
    ChatSessionRepository,
    MutationAuditLogRepository,
    PendingMutationRepository,
    QueryRunRepository,
)
from app.domain.connections.manager import connection_manager
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.projects.services import ProjectService, get_project_service

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """Format an SSE message block with event name and JSON payload."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _build_history_messages(recent_messages: list[ChatMessage]) -> list[BaseMessage]:
    """Convert stored chat messages to LangChain message models."""
    history: list[BaseMessage] = []
    for m in recent_messages[:-1][-MAX_HISTORY_MESSAGES:]:  # Exclude current user message
        if m.role == "user":
            history.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            history.append(AIMessage(content=m.content))
    return history


def _extract_node_event(node_name: str, node_output: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Extract (event_type, payload_dict) for a specific node update in the graph."""
    if node_name == "intent":
        return (
            "intent_classified",
            {
                "intent_type": node_output.get("intent_type"),
                "extracted_entities": node_output.get("extracted_entities"),
            },
        )
    if node_name == "mutation_planner":
        return (
            "mutation_planned",
            {
                "status": node_output.get("mutation_status"),
                "change_set": node_output.get("mutation_change_set"),
            },
        )
    if node_name == "missing_field_collector":
        return (
            "fields_inspected",
            {
                "status": node_output.get("mutation_status"),
                "fields_pending": node_output.get("mutation_fields_pending"),
            },
        )
    if node_name == "mutation_validator":
        return (
            "mutation_validated",
            {
                "status": node_output.get("mutation_status"),
                "error": node_output.get("mutation_validation_error"),
            },
        )
    if node_name == "mutation_previewer":
        return (
            "mutation_staged",
            {
                "mutation_id": str(node_output.get("mutation_id")),
                "status": node_output.get("mutation_status"),
            },
        )
    if node_name == "sql_generator":
        return (
            "sql_generated",
            {
                "generated_sql": node_output.get("generated_sql"),
                "sql_dialect": node_output.get("sql_dialect"),
            },
        )
    if node_name == "sql_executor":
        err = node_output.get("execution_error")
        if err:
            return (
                "sql_error",
                {
                    "error": err,
                    "retry_count": node_output.get("retry_count", 1),
                },
            )
        rows = node_output.get("execution_result", [])
        return (
            "sql_executed",
            {
                "row_count": len(rows),
                "sample_rows": rows[:10],
            },
        )
    if node_name in {
        "result_formatter",
        "error_terminal",
        "general_chat",
        "unsafe_handler",
        "mutation_result_formatter",
    }:
        return (
            "summary_ready",
            {
                "nl_summary": node_output.get("nl_summary"),
            },
        )
    return None


def _format_node_event(node_name: str, node_output: dict[str, Any]) -> str | None:
    """Format SSE event string for a specific node update in the graph."""
    extracted = _extract_node_event(node_name, node_output)
    if extracted is not None:
        event_name, data = extracted
        return _format_sse(event_name, data)
    return None


class ChatService:
    """Domain service managing chat sessions, messages, and agent execution."""

    def __init__(
        self,
        db: AsyncSession,
        project_service: ProjectService,
        connection_service: ConnectionService,
        ws_manager: WebSocketConnectionManager = websocket_manager,
    ) -> None:
        self._db = db
        self._project_service = project_service
        self._connection_service = connection_service
        self._ws_manager = ws_manager
        self._session_repo = ChatSessionRepository(db)
        self._message_repo = ChatMessageRepository(db)
        self._query_run_repo = QueryRunRepository(db)
        self._mutation_repo = PendingMutationRepository(db)
        self._audit_repo = MutationAuditLogRepository(db)

    async def get_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        mutation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PendingMutation:
        """Retrieve a pending mutation ensuring session and project isolation."""
        await self.get_session(project_id=project_id, session_id=session_id, user_id=user_id)
        mutation = await self._mutation_repo.get_by_id_and_project(
            mutation_id=mutation_id,
            project_id=project_id,
        )
        if mutation is None or mutation.session_id != session_id:
            raise NotFoundException(
                detail=f"Pending mutation '{mutation_id}' not found in session.",
                error_code="MUTATION_NOT_FOUND",
            )
        return mutation

    async def list_mutations(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> tuple[list[PendingMutation], int]:
        """List pending mutations for a session with pagination."""
        await self.get_session(project_id=project_id, session_id=session_id, user_id=user_id)
        return await self._mutation_repo.list_by_session(
            session_id=session_id,
            project_id=project_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

    async def approve_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        mutation_id: uuid.UUID,
        user_id: uuid.UUID,
        idempotency_key: str,
        auto_execute: bool = False,
    ) -> PendingMutation:
        """Approve a pending mutation proposal. Strictly enforces project owner permission."""
        project = await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        if project.owner_id != user_id:
            raise ForbiddenException(
                detail="Only the project owner can approve database write mutations.",
                error_code="MUTATION_APPROVAL_FORBIDDEN",
            )

        mutation = await self.get_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=user_id,
        )

        # 1. Status check
        if mutation.status != "PENDING_APPROVAL":
            raise BadRequestException(
                detail=f"Mutation '{mutation_id}' is in status '{mutation.status}', cannot approve.",
                error_code="INVALID_MUTATION_STATUS",
            )

        # 2. Expiration check
        now = datetime.now(tz=UTC)
        if mutation.expires_at < now:
            await self._mutation_repo.update_status(mutation, status="EXPIRED")
            raise BadRequestException(
                detail="Mutation approval window has expired.",
                error_code="MUTATION_EXPIRED",
            )

        # 3. Idempotency check
        if idempotency_key:
            existing = await self._mutation_repo.get_by_idempotency_key(
                idempotency_key=idempotency_key,
                project_id=project_id,
            )
            if existing and existing.id != mutation.id:
                raise ConflictException(
                    detail="Idempotency key has already been used for another mutation.",
                    error_code="IDEMPOTENCY_CONFLICT",
                )
            mutation.idempotency_key = idempotency_key

        # 4. Transition status to APPROVED
        updated = await self._mutation_repo.update_status(
            mutation=mutation,
            status="APPROVED",
            approver_id=user_id,
        )

        # 5. Broadcast WebSocket frame
        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="mutation_approved",
            data={
                "mutation_id": str(updated.id),
                "approver_id": str(user_id),
                "status": "APPROVED",
                "approved_at": updated.approved_at.isoformat() if updated.approved_at else None,
            },
        )

        logger.info(
            "Mutation %s approved by owner %s (session %s)",
            mutation_id,
            user_id,
            session_id,
        )

        if auto_execute:
            return await self.execute_mutation(
                project_id=project_id,
                session_id=session_id,
                mutation_id=mutation_id,
                user_id=user_id,
            )

        return updated

    async def execute_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        mutation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PendingMutation:
        """Execute an approved mutation in a single atomic transaction on the target database."""
        project = await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        if project.owner_id != user_id:
            raise ForbiddenException(
                detail="Only the project owner can execute database write mutations.",
                error_code="MUTATION_EXECUTION_FORBIDDEN",
            )

        mutation = await self.get_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=user_id,
        )

        if mutation.status not in {"APPROVED", "PENDING_APPROVAL"}:
            if mutation.status == "EXECUTED":
                return mutation
            raise BadRequestException(
                detail=f"Mutation '{mutation_id}' is in status '{mutation.status}', cannot execute.",
                error_code="INVALID_MUTATION_STATUS",
            )

        # 1. Decrypt change-set and verify tamper-evident hash
        try:
            plain_json = decrypt_secret(mutation.change_set_encrypted)
            change_set_data = json.loads(plain_json)
        except Exception as exc:
            logger.error("Failed to decrypt change-set for mutation %s: %s", mutation_id, exc)
            raise BadRequestException(
                detail="Failed to decrypt mutation change-set payload.",
                error_code="MUTATION_DECRYPT_FAILED",
            ) from exc

        computed_hash = compute_change_set_hash(change_set_data)
        if computed_hash != mutation.change_set_hash:
            logger.warning(
                "Tamper detection failed for mutation %s: expected %s, got %s",
                mutation_id,
                mutation.change_set_hash,
                computed_hash,
            )
            raise BadRequestException(
                detail="Mutation payload tamper detection triggered: hash mismatch.",
                error_code="MUTATION_TAMPER_DETECTED",
            )

        # 2. Transition status to EXECUTING
        await self._mutation_repo.update_status(
            mutation=mutation,
            status="EXECUTING",
            approver_id=user_id,
        )

        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="mutation_executing",
            data={
                "mutation_id": str(mutation.id),
                "status": "EXECUTING",
            },
        )

        # 3. Acquire connection engine
        connection = await self._connection_service.get_connection(
            project_id=project_id,
            user_id=user_id,
        )
        engine = connection_manager.get_engine(
            project_id=project_id,
            connection_id=connection.id,
            encrypted_connection_string=connection.encrypted_connection_string,
        )

        # 4. Execute change-set within atomic transaction
        exec_res = await execute_change_set(
            engine=engine,
            dialect=connection.dialect,
            change_set=change_set_data,
            preview_row_counts=mutation.preview_row_counts,
        )

        ops = {m.get("operation", "insert").lower() for m in change_set_data.get("mutations", [])}
        op_label = "multi_write" if len(ops) > 1 else (list(ops)[0] if ops else "insert")

        if exec_res.success:
            result_encrypted = encrypt_secret(json.dumps(exec_res.tables_affected))
            updated = await self._mutation_repo.update_status(
                mutation=mutation,
                status="EXECUTED",
                total_rows_affected=exec_res.total_rows_affected,
                execution_result_encrypted=result_encrypted,
            )

            # Record append-only audit log
            await self._audit_repo.create_log(
                project_id=project_id,
                connection_id=connection.id,
                mutation_id=mutation.id,
                initiator_id=mutation.proposer_id,
                approver_id=user_id,
                operation=op_label,
                change_set_hash=mutation.change_set_hash,
                status="executed",
                tables_affected=exec_res.tables_affected,
                total_rows_affected=exec_res.total_rows_affected,
                before_snapshot_encrypted=exec_res.before_snapshot_encrypted,
                after_snapshot_encrypted=exec_res.after_snapshot_encrypted,
                latency_ms=exec_res.latency_ms,
            )

            # Broadcast WebSocket frame
            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="mutation_executed",
                data={
                    "mutation_id": str(updated.id),
                    "status": "EXECUTED",
                    "total_rows_affected": exec_res.total_rows_affected,
                    "tables_affected": exec_res.tables_affected,
                    "latency_ms": exec_res.latency_ms,
                    "summary": f"Executed: {change_set_data.get('summary', '')}",
                },
            )

            # Persist assistant confirmation message
            await self._message_repo.create_message(
                session_id=session_id,
                project_id=project_id,
                role="assistant",
                content=(
                    f"Database transaction executed successfully: {change_set_data.get('summary', '')}. "
                    f"{exec_res.total_rows_affected} row(s) affected across {len(exec_res.tables_affected)} table(s)."
                ),
                metadata_json={
                    "mutation_id": str(updated.id),
                    "status": "EXECUTED",
                    "tables_affected": exec_res.tables_affected,
                    "total_rows_affected": exec_res.total_rows_affected,
                    "latency_ms": exec_res.latency_ms,
                },
            )

            logger.info(
                "Mutation %s successfully EXECUTED (%d rows, %d ms)",
                mutation_id,
                exec_res.total_rows_affected,
                exec_res.latency_ms,
            )
            return updated

        else:
            updated = await self._mutation_repo.update_status(
                mutation=mutation,
                status="FAILED",
            )

            # Record append-only audit log
            await self._audit_repo.create_log(
                project_id=project_id,
                connection_id=connection.id,
                mutation_id=mutation.id,
                initiator_id=mutation.proposer_id,
                approver_id=user_id,
                operation=op_label,
                change_set_hash=mutation.change_set_hash,
                status="failed",
                tables_affected=exec_res.tables_affected,
                total_rows_affected=0,
                before_snapshot_encrypted=exec_res.before_snapshot_encrypted,
                error_details=exec_res.error_message,
                latency_ms=exec_res.latency_ms,
            )

            # Broadcast WebSocket frame
            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="mutation_failed",
                data={
                    "mutation_id": str(updated.id),
                    "status": "FAILED",
                    "error": exec_res.error_message,
                },
            )

            # Record failure timestamp to activate 60s session cooldown (Phase 7)
            mutation_rate_limiter.record_failure(session_id=session_id)

            logger.error(
                "Mutation %s execution FAILED: %s",
                mutation_id,
                exec_res.error_message,
            )
            return updated

    async def list_audit_logs(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> tuple[list[MutationAuditLog], int]:
        """List immutable audit log records for a project with total count."""
        await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        return await self._audit_repo.list_by_project(
            project_id=project_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )

    async def undo_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        mutation_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> PendingMutation:
        """Soft-undo an executed mutation within the configured connection undo window (Phase 7)."""
        project = await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        if project.owner_id != user_id:
            raise ForbiddenException(
                detail="Only the project owner can revert/undo database write mutations.",
                error_code="MUTATION_UNDO_FORBIDDEN",
            )

        mutation = await self.get_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=user_id,
        )

        if mutation.status != "EXECUTED":
            raise BadRequestException(
                detail=f"Mutation '{mutation_id}' is in status '{mutation.status}', only EXECUTED mutations can be undone.",
                error_code="INVALID_MUTATION_STATUS",
            )

        connection = await self._connection_service.get_connection(
            project_id=project_id,
            user_id=user_id,
        )

        undo_window = getattr(connection, "undo_window_minutes", 0) or 0
        if undo_window <= 0:
            raise BadRequestException(
                detail="Soft-undo is disabled on this database connection (undo_window_minutes is 0).",
                error_code="UNDO_DISABLED",
            )

        # Check undo window expiration
        now = datetime.now(tz=UTC)
        executed_time = mutation.executed_at or mutation.updated_at
        if executed_time and (now - executed_time) > timedelta(minutes=undo_window):
            raise BadRequestException(
                detail=f"The {undo_window}-minute undo window for this mutation has expired.",
                error_code="UNDO_WINDOW_EXPIRED",
            )

        # Decrypt change-set and snapshots
        try:
            plain_json = decrypt_secret(mutation.change_set_encrypted)
            change_set_data = json.loads(plain_json)
        except Exception as exc:
            logger.error("Failed to decrypt change-set for undo: %s", exc)
            raise BadRequestException(
                detail="Failed to decrypt change-set for undo.",
                error_code="UNDO_DECRYPT_FAILED",
            ) from exc

        before_snapshots: dict[str, list[dict[str, Any]]] = {}
        if mutation.audit_logs:
            for log in mutation.audit_logs:
                if log.status == "executed" and log.before_snapshot_encrypted:
                    try:
                        snap_json = decrypt_secret(log.before_snapshot_encrypted)
                        before_snapshots = json.loads(snap_json)
                        break
                    except Exception as snap_err:
                        logger.warning("Could not decrypt before_snapshot for undo: %s", snap_err)

        engine = connection_manager.get_engine(
            project_id=project_id,
            connection_id=connection.id,
            encrypted_connection_string=connection.encrypted_connection_string,
        )

        undo_res = await execute_undo_change_set(
            engine=engine,
            dialect=connection.dialect,
            change_set=change_set_data,
            before_snapshots=before_snapshots,
        )

        if undo_res.success:
            updated = await self._mutation_repo.update_status(
                mutation=mutation,
                status="UNDONE",
            )

            await self._audit_repo.create_log(
                project_id=project_id,
                connection_id=connection.id,
                mutation_id=mutation.id,
                initiator_id=mutation.proposer_id,
                approver_id=user_id,
                operation="undo",
                change_set_hash=mutation.change_set_hash,
                status="undone",
                tables_affected=undo_res.tables_affected,
                total_rows_affected=undo_res.total_rows_affected,
                error_details=reason,
                latency_ms=undo_res.latency_ms,
            )

            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="mutation_undone",
                data={
                    "mutation_id": str(updated.id),
                    "status": "UNDONE",
                    "total_rows_reverted": undo_res.total_rows_affected,
                    "tables_affected": undo_res.tables_affected,
                    "reason": reason,
                },
            )

            await self._message_repo.create_message(
                session_id=session_id,
                project_id=project_id,
                role="assistant",
                content=(
                    f"Database transaction was successfully undone/reverted: {change_set_data.get('summary', '')}. "
                    f"{undo_res.total_rows_affected} row(s) reverted."
                ),
                metadata_json={
                    "mutation_id": str(updated.id),
                    "status": "UNDONE",
                    "reason": reason,
                },
            )

            logger.info("Mutation %s successfully UNDONE by owner %s", mutation_id, user_id)
            return updated

        else:
            await self._audit_repo.create_log(
                project_id=project_id,
                connection_id=connection.id,
                mutation_id=mutation.id,
                initiator_id=mutation.proposer_id,
                approver_id=user_id,
                operation="undo",
                change_set_hash=mutation.change_set_hash,
                status="failed",
                tables_affected=undo_res.tables_affected,
                total_rows_affected=0,
                error_details=undo_res.error_message,
                latency_ms=undo_res.latency_ms,
            )

            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="mutation_undo_failed",
                data={
                    "mutation_id": str(mutation.id),
                    "status": "FAILED",
                    "error": undo_res.error_message,
                },
            )

            raise BadRequestException(
                detail=f"Soft-undo failed: {undo_res.error_message}. Underlying dependencies or table states may prevent rollback.",
                error_code="UNDO_EXECUTION_FAILED",
            )

    async def reject_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        mutation_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> PendingMutation:
        """Reject a pending mutation proposal."""
        project = await self._project_service.get_project(project_id=project_id, owner_id=user_id)
        if project.owner_id != user_id:
            raise ForbiddenException(
                detail="Only the project owner can reject database write mutations.",
                error_code="MUTATION_REJECTION_FORBIDDEN",
            )

        mutation = await self.get_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=user_id,
        )

        if mutation.status != "PENDING_APPROVAL":
            raise BadRequestException(
                detail=f"Mutation '{mutation_id}' is in status '{mutation.status}', cannot reject.",
                error_code="INVALID_MUTATION_STATUS",
            )

        updated = await self._mutation_repo.update_status(
            mutation=mutation,
            status="REJECTED",
            approver_id=user_id,
        )

        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="mutation_rejected",
            data={
                "mutation_id": str(updated.id),
                "rejector_id": str(user_id),
                "status": "REJECTED",
                "reason": reason,
            },
        )

        logger.info(
            "Mutation %s rejected by owner %s (reason: %s)",
            mutation_id,
            user_id,
            reason,
        )
        return updated

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
        dry_run: bool = False,
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
                "dry_run": dry_run,
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
            # The current message is included in the query result, so fetch one
            # extra row to retain at most MAX_HISTORY_MESSAGES previous messages.
            limit=MAX_HISTORY_MESSAGES + 1,
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
            "dry_run": dry_run,
        }

        # 6. Stream graph execution step-by-step
        final_state: dict[str, Any] = dict(initial_state)

        logger.info(
            "==================== LANGGRAPH EXECUTION START ====================\n"
            "  Session ID: %s\n"
            "  Project ID: %s\n"
            "  User Query: %s\n"
            "  Dialect: %s\n"
            "==================================================================",
            session_id,
            project_id,
            content,
            deps.connection.dialect,
        )

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

        logger.info(
            "==================== LANGGRAPH EXECUTION END ====================\n"
            "  Status: %s\n"
            "  Latency: %dms\n"
            "  Generated SQL:\n    %s\n"
            "  Rows Returned: %d\n"
            "  Final Summary:\n    %s\n"
            "==================================================================",
            execution_status.upper(),
            latency_ms,
            final_state.get("generated_sql") or "<NONE>",
            len(final_state.get("execution_result", [])),
            final_state.get("nl_summary") or "<NONE>",
        )

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

    async def send_message_websocket(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        dry_run: bool = False,
    ) -> None:
        """Process a user question through the LangGraph agent pipeline and dispatch events via WebSocket."""
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

        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="message_received",
            data={
                "message_id": str(user_msg.id),
                "role": "user",
                "content": content,
                "dry_run": dry_run,
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
            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="error",
                data={"message": f"Initialization failed: {exc}"},
            )
            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="done",
                data={},
            )
            return

        # 4. Fetch recent messages for multi-turn context
        recent_messages = await self._message_repo.get_recent_messages(
            session_id=session_id,
            project_id=project_id,
            limit=MAX_HISTORY_MESSAGES + 1,
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
            "dry_run": dry_run,
        }

        # 6. Stream graph execution step-by-step
        final_state: dict[str, Any] = dict(initial_state)

        logger.info(
            "==================== LANGGRAPH WS EXECUTION START ====================\n"
            "  Session ID: %s\n"
            "  Project ID: %s\n"
            "  User Query: %s\n"
            "  Dialect: %s\n"
            "=====================================================================",
            session_id,
            project_id,
            content,
            deps.connection.dialect,
        )

        try:
            async for update in graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in update.items():
                    if not isinstance(node_output, dict):
                        continue
                    final_state.update(node_output)
                    extracted = _extract_node_event(node_name, node_output)
                    if extracted is not None:
                        event_type, payload = extracted
                        await self._ws_manager.send_event(
                            session_id=session_id,
                            event_type=event_type,
                            data=payload,
                        )

        except Exception as graph_err:
            logger.exception("LangGraph WS execution error: %s", graph_err)
            final_state["execution_error"] = str(graph_err)
            final_state["nl_summary"] = f"An unexpected error occurred during execution: {graph_err}"
            await self._ws_manager.send_event(
                session_id=session_id,
                event_type="error",
                data={"message": str(graph_err)},
            )

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
        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="final_result",
            data={
                "assistant_message_id": str(assistant_msg.id),
                "query_run_id": str(query_run.id),
                "content": assistant_msg.content,
                "generated_sql": final_state.get("generated_sql"),
                "execution_result": final_state.get("execution_result", []),
                "status": execution_status,
                "latency_ms": latency_ms,
            },
        )

        await self._ws_manager.send_event(
            session_id=session_id,
            event_type="done",
            data={},
        )


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
