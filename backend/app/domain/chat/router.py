"""
Chat domain — FastAPI HTTP router (Phase 10).

Exposes endpoints for chat session lifecycle, message history, and real-time SSE
message streaming with the LangGraph agent pipeline.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.core.responses import (
    ApiResponse,
    PaginatedData,
    paginated_response,
    success_response,
)
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import Pagination
from app.domain.auth.models import User
from app.domain.chat.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
)
from app.domain.chat.services import ChatService, get_chat_service

router = APIRouter()


@router.post(
    "/{project_id}/chat/sessions",
    response_model=ApiResponse[ChatSessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Chat Session",
)
async def create_chat_session(
    project_id: uuid.UUID,
    payload: ChatSessionCreate,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ChatSessionResponse]:
    """Create a new chat session for a project."""
    session = await service.create_session(
        project_id=project_id,
        user_id=current_user.id,
        title=payload.title,
    )
    return success_response(
        data=ChatSessionResponse.model_validate(session),
        message="Chat session created successfully.",
    )


@router.get(
    "/{project_id}/chat/sessions",
    response_model=ApiResponse[PaginatedData[ChatSessionResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Chat Sessions",
)
async def list_chat_sessions(
    project_id: uuid.UUID,
    pagination: Pagination,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[PaginatedData[ChatSessionResponse]]:
    """List all chat sessions for a project with pagination."""
    items, total = await service.list_sessions(
        project_id=project_id,
        user_id=current_user.id,
        pagination=pagination,
    )
    response_items = [ChatSessionResponse.model_validate(s) for s in items]
    return paginated_response(
        items=response_items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        message="Chat sessions retrieved successfully.",
    )


@router.get(
    "/{project_id}/chat/sessions/{session_id}",
    response_model=ApiResponse[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Chat Session",
)
async def get_chat_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ChatSessionResponse]:
    """Retrieve details for a single chat session."""
    session = await service.get_session(
        project_id=project_id,
        session_id=session_id,
        user_id=current_user.id,
    )
    return success_response(
        data=ChatSessionResponse.model_validate(session),
        message="Chat session retrieved successfully.",
    )


@router.patch(
    "/{project_id}/chat/sessions/{session_id}",
    response_model=ApiResponse[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Update Chat Session Title",
)
async def update_chat_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: ChatSessionUpdate,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ChatSessionResponse]:
    """Update title of a chat session."""
    session = await service.update_session_title(
        project_id=project_id,
        session_id=session_id,
        user_id=current_user.id,
        title=payload.title,
    )
    return success_response(
        data=ChatSessionResponse.model_validate(session),
        message="Chat session title updated successfully.",
    )


@router.delete(
    "/{project_id}/chat/sessions/{session_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete Chat Session",
)
async def delete_chat_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[None]:
    """Delete a chat session and all associated messages and query runs."""
    await service.delete_session(
        project_id=project_id,
        session_id=session_id,
        user_id=current_user.id,
    )
    return success_response(
        data=None,
        message="Chat session deleted successfully.",
    )


@router.get(
    "/{project_id}/chat/sessions/{session_id}/messages",
    response_model=ApiResponse[PaginatedData[ChatMessageResponse]],
    status_code=status.HTTP_200_OK,
    summary="List Chat Messages",
)
async def list_chat_messages(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    pagination: Pagination,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[PaginatedData[ChatMessageResponse]]:
    """List messages within a chat session with pagination."""
    items, total = await service.list_messages(
        project_id=project_id,
        session_id=session_id,
        user_id=current_user.id,
        pagination=pagination,
    )
    response_items = [ChatMessageResponse.model_validate(m) for m in items]
    return paginated_response(
        items=response_items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        message="Chat messages retrieved successfully.",
    )


@router.post(
    "/{project_id}/chat/sessions/{session_id}/messages",
    summary="Send Message (SSE Stream)",
)
async def send_chat_message(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: ChatMessageRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> StreamingResponse:
    """Send a natural language query and stream real-time agent execution events via SSE."""
    stream_generator = service.send_message_stream(
        project_id=project_id,
        session_id=session_id,
        user_id=current_user.id,
        content=payload.content,
    )

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
