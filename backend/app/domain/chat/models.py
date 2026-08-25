"""
Chat domain — SQLAlchemy ORM models.

Contains:
- `ChatSession`: multi-turn conversational session for a project and connection.
- `ChatMessage`: message turns within a session (user, assistant, system).
- `QueryRun`: SQL generation and execution attempt records, supporting retry chains.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
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
