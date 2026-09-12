"""
Chat domain — FastAPI HTTP router (Phase 10).

Exposes endpoints for chat session lifecycle, message history, and real-time SSE
message streaming with the LangGraph agent pipeline.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncGenerator

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.responses import (
    ApiResponse,
    PaginatedData,
    paginated_response,
    success_response,
)
from app.core.security import verify_token
from app.core.websocket import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_NORMAL,
    WS_CLOSE_SESSION_NOT_FOUND,
    WS_CLOSE_UNAUTHORIZED,
    websocket_manager,
)
from app.db.session import _get_session_factory
from app.dependencies.auth import get_current_active_user
from app.dependencies.pagination import Pagination
from app.domain.auth.models import User
from app.domain.auth.repository import UserRepository
from app.domain.chat.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
)
from app.domain.chat.services import ChatService, get_chat_service
from app.domain.connections.manager import connection_manager
from app.domain.connections.services import ConnectionService
from app.domain.projects.services import ProjectService

logger = logging.getLogger(__name__)

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
    summary="Send Message (SSE Stream) [Deprecated]",
    deprecated=True,
)
async def send_chat_message(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: ChatMessageRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> StreamingResponse:
    """Send a natural language query and stream real-time agent execution events via SSE.

    .. deprecated::
        Use the WebSocket endpoint at ``/{project_id}/chat/sessions/{session_id}/ws``
        for bidirectional real-time communication.
    """
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


@asynccontextmanager
async def _get_chat_service_context(project_id: uuid.UUID) -> AsyncGenerator[tuple[AsyncSession, ChatService], None]:
    """Helper context manager to supply AsyncSession and ChatService inside a WebSocket handler."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            proj_svc = ProjectService(session)
            conn_svc = ConnectionService(session, proj_svc, connection_manager)
            chat_svc = ChatService(
                db=session,
                project_service=proj_svc,
                connection_service=conn_svc,
                ws_manager=websocket_manager,
            )
            yield session, chat_svc
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@router.websocket("/{project_id}/chat/sessions/{session_id}/ws")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    token: str = Query(..., description="JWT authentication access token"),
    last_seq: int | None = Query(None, description="Last received sequence number for replay"),
) -> None:
    """WebSocket endpoint for bidirectional real-time chat and HITL communication.

    - Authenticates the user via JWT query parameter.
    - Replays missed events if ``last_seq`` is provided.
    - Handles incoming JSON frames: ``message``, ``ping``.
    """
    # 1. Authenticate user from JWT token
    try:
        payload = verify_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Missing subject in token")
            return
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid or expired token")
        return

    # 2. Verify user and session existence & project ownership
    async with _get_chat_service_context(project_id) as (db_session, chat_service):
        user_repo = UserRepository(db_session)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="User inactive or not found")
            return

        try:
            await chat_service.get_session(
                project_id=project_id,
                session_id=session_id,
                user_id=user_id,
            )
        except NotFoundException:
            await websocket.close(code=WS_CLOSE_SESSION_NOT_FOUND, reason="Chat session not found")
            return
        except ForbiddenException:
            await websocket.close(code=WS_CLOSE_FORBIDDEN, reason="Access to project denied")
            return

    # 3. Accept connection and register with connection manager
    await websocket_manager.connect(
        websocket=websocket,
        project_id=project_id,
        session_id=session_id,
        user_id=user_id,
    )

    # 4. Handle optional event replay on reconnect
    if last_seq is not None:
        await websocket_manager.replay_events_since(
            session_id=session_id,
            last_sequence=last_seq,
        )

    # 5. Event processing loop
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                frame_data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket_manager.send_event(
                    session_id=session_id,
                    event_type="error",
                    data={"message": "Invalid JSON frame received."},
                )
                continue

            frame_type = frame_data.get("type")

            if frame_type == "ping":
                await websocket_manager.send_event(
                    session_id=session_id,
                    event_type="pong",
                    data={},
                )

            elif frame_type == "message":
                content = frame_data.get("content")
                if not content or not isinstance(content, str) or not content.strip():
                    await websocket_manager.send_event(
                        session_id=session_id,
                        event_type="error",
                        data={"message": "Message content cannot be empty."},
                    )
                    continue

                # Process query through agent and dispatch via WebSocket
                async with _get_chat_service_context(project_id) as (_, chat_service):
                    await chat_service.send_message_websocket(
                        project_id=project_id,
                        session_id=session_id,
                        user_id=user_id,
                        content=content.strip(),
                    )

            else:
                logger.debug("Received unhandled or future frame type: %s", frame_type)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected gracefully for session %s", session_id)
    except Exception as exc:
        logger.exception("Unexpected error in WebSocket loop for session %s: %s", session_id, exc)
    finally:
        await websocket_manager.disconnect(session_id=session_id)
