"""
Chat domain — Data access layer (Phase 9).

Encapsulates database operations for ChatSession, ChatMessage, and QueryRun entities,
strictly enforcing multi-tenant project_id scoping across all queries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.chat.models import (
    ChatMessage,
    ChatSession,
    MutationAuditLog,
    PendingMutation,
    QueryRun,
)


class ChatSessionRepository:
    """Repository managing ChatSession persistence and queries."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id_and_project(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> ChatSession | None:
        """Fetch a chat session by ID ensuring project isolation."""
        stmt = (
            select(ChatSession)
            .where(
                ChatSession.id == session_id,
                ChatSession.project_id == project_id,
            )
            .options(
                selectinload(ChatSession.messages).selectinload(ChatMessage.selected_query_run)
            )
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ChatSession], int]:
        """List chat sessions for a project with total count."""
        count_stmt = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.project_id == project_id)
        )
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(ChatSession)
            .where(ChatSession.project_id == project_id)
            .order_by(desc(ChatSession.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def create_session(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatSession:
        """Create and persist a new chat session."""
        session = ChatSession(
            project_id=project_id,
            connection_id=connection_id,
            title=title,
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def update_title(
        self,
        session: ChatSession,
        title: str | None,
    ) -> ChatSession:
        """Update session title."""
        session.title = title
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def delete_session(self, session: ChatSession) -> None:
        """Delete a chat session and cascade delete its messages and query runs."""
        await self._db.delete(session)
        await self._db.commit()


class ChatMessageRepository:
    """Repository managing ChatMessage persistence and queries."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_message(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID,
        role: str,
        content: str,
        query_run_id: uuid.UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
        token_count: int | None = None,
    ) -> ChatMessage:
        """Create and persist a new chat message."""
        msg = ChatMessage(
            session_id=session_id,
            project_id=project_id,
            role=role,
            content=content,
            query_run_id=query_run_id,
            metadata_json=metadata_json,
            token_count=token_count,
        )
        self._db.add(msg)
        await self._db.commit()
        await self._db.refresh(msg)
        return msg

    async def list_by_session(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ChatMessage], int]:
        """List messages for a session with pagination."""
        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.project_id == project_id,
            )
        )
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.project_id == project_id,
            )
            .options(selectinload(ChatMessage.selected_query_run))
            .order_by(ChatMessage.created_at)
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_recent_messages(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ChatMessage]:
        """Fetch recent messages in chronological order for conversation memory."""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.project_id == project_id,
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows


class QueryRunRepository:
    """Repository managing QueryRun records for execution attempts."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_query_run(
        self,
        chat_message_id: uuid.UUID,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        nl_prompt: str,
        generated_sql: str | None = None,
        status: str = "pending",
        error_message: str | None = None,
        result_summary: str | None = None,
        result_row_count: int | None = None,
        latency_ms: int | None = None,
        attempt_number: int = 1,
        parent_run_id: uuid.UUID | None = None,
    ) -> QueryRun:
        """Create and persist a QueryRun record."""
        run = QueryRun(
            chat_message_id=chat_message_id,
            project_id=project_id,
            connection_id=connection_id,
            attempt_number=attempt_number,
            parent_run_id=parent_run_id,
            nl_prompt=nl_prompt,
            generated_sql=generated_sql,
            status=status,
            error_message=error_message,
            result_summary=result_summary,
            result_row_count=result_row_count,
            latency_ms=latency_ms,
        )
        self._db.add(run)
        await self._db.commit()
        await self._db.refresh(run)
        return run


class PendingMutationRepository:
    """Repository managing PendingMutation persistence, querying, and lifecycle status transitions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_mutation(
        self,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        connection_id: uuid.UUID,
        proposer_id: uuid.UUID,
        change_set_encrypted: str,
        change_set_hash: str,
        expires_at: datetime,
        preview_row_counts: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        status: str = "PENDING_APPROVAL",
    ) -> PendingMutation:
        """Create and persist a staged mutation proposal."""
        mutation = PendingMutation(
            project_id=project_id,
            session_id=session_id,
            connection_id=connection_id,
            proposer_id=proposer_id,
            change_set_encrypted=change_set_encrypted,
            change_set_hash=change_set_hash,
            expires_at=expires_at,
            preview_row_counts=preview_row_counts,
            idempotency_key=idempotency_key,
            status=status,
        )
        self._db.add(mutation)
        await self._db.flush()
        await self._db.refresh(mutation)
        return mutation

    async def get_by_id_and_project(
        self,
        mutation_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PendingMutation | None:
        """Fetch pending mutation by ID enforcing multi-tenant isolation."""
        stmt = select(PendingMutation).where(
            PendingMutation.id == mutation_id,
            PendingMutation.project_id == project_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
        project_id: uuid.UUID,
    ) -> PendingMutation | None:
        """Fetch mutation by unique idempotency key."""
        stmt = select(PendingMutation).where(
            PendingMutation.idempotency_key == idempotency_key,
            PendingMutation.project_id == project_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        mutation: PendingMutation,
        status: str,
        approver_id: uuid.UUID | None = None,
        total_rows_affected: int | None = None,
        execution_result_encrypted: str | None = None,
    ) -> PendingMutation:
        """Update lifecycle status and execution outcomes on a mutation."""
        now = datetime.now(tz=UTC)
        mutation.status = status
        if approver_id is not None:
            mutation.approver_id = approver_id
        if status == "APPROVED":
            mutation.approved_at = now
        elif status in {"EXECUTED", "FAILED"}:
            mutation.executed_at = now
        if total_rows_affected is not None:
            mutation.total_rows_affected = total_rows_affected
        if execution_result_encrypted is not None:
            mutation.execution_result_encrypted = execution_result_encrypted

        await self._db.flush()
        await self._db.refresh(mutation)
        return mutation

    async def list_by_session(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PendingMutation], int]:
        """List pending mutations for a session with total count."""
        count_stmt = (
            select(func.count())
            .select_from(PendingMutation)
            .where(
                PendingMutation.session_id == session_id,
                PendingMutation.project_id == project_id,
            )
        )
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(PendingMutation)
            .where(
                PendingMutation.session_id == session_id,
                PendingMutation.project_id == project_id,
            )
            .order_by(desc(PendingMutation.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total


class MutationAuditLogRepository:
    """Repository managing append-only MutationAuditLog records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_log(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        initiator_id: uuid.UUID,
        operation: str,
        change_set_hash: str,
        status: str,
        mutation_id: uuid.UUID | None = None,
        approver_id: uuid.UUID | None = None,
        tables_affected: list[dict[str, Any]] | None = None,
        total_rows_affected: int = 0,
        before_snapshot_encrypted: str | None = None,
        after_snapshot_encrypted: str | None = None,
        error_details: str | None = None,
        latency_ms: int | None = None,
    ) -> MutationAuditLog:
        """Append an immutable audit entry for an executed or attempted write."""
        log_entry = MutationAuditLog(
            project_id=project_id,
            connection_id=connection_id,
            mutation_id=mutation_id,
            initiator_id=initiator_id,
            approver_id=approver_id,
            operation=operation,
            tables_affected=tables_affected,
            total_rows_affected=total_rows_affected,
            change_set_hash=change_set_hash,
            before_snapshot_encrypted=before_snapshot_encrypted,
            after_snapshot_encrypted=after_snapshot_encrypted,
            status=status,
            error_details=error_details,
            latency_ms=latency_ms,
        )
        self._db.add(log_entry)
        await self._db.flush()
        await self._db.refresh(log_entry)
        return log_entry

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[MutationAuditLog], int]:
        """List audit entries for a project with total count."""
        count_stmt = (
            select(func.count())
            .select_from(MutationAuditLog)
            .where(MutationAuditLog.project_id == project_id)
        )
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = (
            select(MutationAuditLog)
            .where(MutationAuditLog.project_id == project_id)
            .order_by(desc(MutationAuditLog.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total
