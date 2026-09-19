"""
Chat domain — SQLAlchemy ORM models.

Contains:
- `ChatSession`: multi-turn conversational session for a project and connection.
- `ChatMessage`: message turns within a session (user, assistant, system).
- `QueryRun`: SQL generation and execution attempt records, supporting retry chains.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    desc,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:
    from app.domain.connections.models import Connection
    from app.domain.projects.models import Project


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_project_created", "project_id", desc("created_at")),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="chat_sessions")
    connection: Mapped[Connection] = relationship("Connection", back_populates="chat_sessions")
    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(CreatedAtMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB, name="metadata", nullable=True
    )
    query_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "query_runs.id",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
    query_runs: Mapped[list[QueryRun]] = relationship(
        "QueryRun",
        back_populates="chat_message",
        cascade="all, delete-orphan",
        foreign_keys="[QueryRun.chat_message_id]",
    )
    selected_query_run: Mapped[QueryRun | None] = relationship(
        "QueryRun",
        foreign_keys=[query_run_id],
        post_update=True,
    )


class QueryRun(TimestampMixin, Base):
    __tablename__ = "query_runs"
    __table_args__ = (
        Index("ix_query_runs_project_created", "project_id", desc("created_at")),
    )

    chat_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nl_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )  # "pending" | "running" | "success" | "correcting" | "failed" | "cancelled" | "timeout"
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chat_message: Mapped[ChatMessage] = relationship(
        "ChatMessage",
        back_populates="query_runs",
        foreign_keys=[chat_message_id],
    )
    parent_run: Mapped[QueryRun | None] = relationship(
        "QueryRun",
        remote_side="QueryRun.id",
        back_populates="child_runs",
    )
    child_runs: Mapped[list[QueryRun]] = relationship(
        "QueryRun",
        back_populates="parent_run",
    )


class PendingMutation(TimestampMixin, Base):
    """Represents a staged multi-table database mutation awaiting owner approval."""

    __tablename__ = "pending_mutations"
    __table_args__ = (
        Index("ix_pending_mutations_session_created", "session_id", desc("created_at")),
        Index("ix_pending_mutations_status", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status: "COLLECTING_INPUT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "EXPIRED" | "EXECUTING" | "EXECUTED" | "FAILED"
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL", nullable=False)

    # Encrypted JSON of change-set proposal
    change_set_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    change_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256

    preview_row_counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_rows_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_result_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[ChatSession] = relationship("ChatSession")
    audit_logs: Mapped[list[MutationAuditLog]] = relationship(
        "MutationAuditLog", back_populates="mutation", cascade="all, delete-orphan"
    )


class MutationAuditLog(CreatedAtMixin, Base):
    """Immutable, append-only record of executed or attempted write operations."""

    __tablename__ = "mutation_audit_logs"
    __table_args__ = (
        Index("ix_mutation_audit_logs_project_created", "project_id", desc("created_at")),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mutation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pending_mutations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Operation: "insert" | "patch" | "multi_write" | "undo"
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    tables_affected: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    total_rows_affected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    change_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    before_snapshot_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_snapshot_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: "executed" | "failed" | "undone"
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    mutation: Mapped[PendingMutation | None] = relationship("PendingMutation", back_populates="audit_logs")
