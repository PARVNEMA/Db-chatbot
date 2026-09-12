"""
Chat domain — Pydantic v2 request/response schemas (Phase 9).

Defines schemas for chat session management, multi-turn conversation messages,
and real-time Server-Sent Event (SSE) payload shapes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    """Payload for creating a new chat session."""

    title: str | None = Field(default=None, max_length=500, description="Optional conversation title")


class ChatSessionUpdate(BaseModel):
    """Payload for updating session metadata."""

    title: str | None = Field(default=None, max_length=500, description="Updated session title")


class ChatSessionResponse(BaseModel):
    """Response representation of a chat session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailResponse(BaseModel):
    """Detailed chat session response including message count."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID
    title: str | None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class QueryRunResponse(BaseModel):
    """Details of a single SQL generation and execution attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_message_id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID
    attempt_number: int
    parent_run_id: uuid.UUID | None
    nl_prompt: str
    generated_sql: str | None
    status: str
    error_message: str | None
    result_summary: str | None
    result_row_count: int | None
    latency_ms: int | None
    created_at: datetime


class ChatMessageRequest(BaseModel):
    """Payload for sending a natural language message in a chat session."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language question or instruction for the database agent.",
    )


class ChatMessageResponse(BaseModel):
    """Response representation of a message turn."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    project_id: uuid.UUID
    role: str
    content: str
    token_count: int | None = None
    metadata_json: dict[str, Any] | None = None
    query_run_id: uuid.UUID | None = None
    created_at: datetime
    selected_query_run: QueryRunResponse | None = None


class SSEEventData(BaseModel):
    """Structured SSE event payload streamed to client during agent processing."""

    event: str
    data: dict[str, Any]


class PendingMutationResponse(BaseModel):
    """Response representation of a staged pending mutation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    session_id: uuid.UUID
    connection_id: uuid.UUID
    proposer_id: uuid.UUID
    approver_id: uuid.UUID | None = None
    status: str
    change_set_hash: str
    preview_row_counts: dict[str, Any] | None = None
    total_rows_affected: int | None = None
    idempotency_key: str | None = None
    expires_at: datetime
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MutationAuditLogResponse(BaseModel):
    """Response representation of an append-only audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID
    mutation_id: uuid.UUID | None = None
    initiator_id: uuid.UUID
    approver_id: uuid.UUID | None = None
    operation: str
    tables_affected: list[dict[str, Any]] | None = None
    total_rows_affected: int
    change_set_hash: str
    status: str
    error_details: str | None = None
    latency_ms: int | None = None
    created_at: datetime


class MutationApproveRequest(BaseModel):
    """Payload for approving a pending mutation."""

    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Client-generated key to prevent duplicate mutation executions.",
    )


class MutationRejectRequest(BaseModel):
    """Payload for rejecting a pending mutation."""

    reason: str | None = Field(default=None, max_length=500, description="Optional rejection explanation")
