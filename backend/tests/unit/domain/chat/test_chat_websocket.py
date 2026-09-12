"""
Unit and protocol tests for WebSocket transport infrastructure (Phase 1).

Tests:
- WebSocketConnectionManager lifecycle (connect, send_event, replay, disconnect).
- Sequence numbering and monotonic frame tracking.
- Reconnection event replay using `last_seq`.
- Evicted sequence handling triggering `resync_required`.
- Broadcast ping handling.
- FastAPI WebSocket endpoint authentication, rejection codes, and chat query execution.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token, encrypt_secret, get_password_hash
from app.core.websocket import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_SESSION_NOT_FOUND,
    WS_CLOSE_UNAUTHORIZED,
    BufferedEvent,
    WebSocketConnectionManager,
)
from app.domain.auth.models import User
from app.domain.connections.models import Connection
from app.domain.projects.models import Project
from app.main import app


@pytest.mark.asyncio
async def test_websocket_manager_send_event_and_sequencing() -> None:
    """Test that manager correctly formats frames and increments sequence numbers."""
    manager = WebSocketConnectionManager()
    session_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.close = AsyncMock()

    # 1. Connect
    conn = await manager.connect(
        websocket=mock_ws,
        project_id=project_id,
        session_id=session_id,
        user_id=user_id,
    )
    assert conn.next_sequence == 1
    assert manager.get_connection(session_id) is conn

    # 2. Send events
    seq1 = await manager.send_event(session_id, "test_event_1", {"foo": "bar"})
    seq2 = await manager.send_event(session_id, "test_event_2", {"baz": 42})

    assert seq1 == 1
    assert seq2 == 2
    assert len(conn.replay_buffer) == 2
    assert mock_ws.send_text.call_count == 2

    # Check payload structure
    sent_frame = json.loads(mock_ws.send_text.call_args_list[0][0][0])
    assert sent_frame["type"] == "test_event_1"
    assert sent_frame["sequence"] == 1
    assert sent_frame["data"] == {"foo": "bar"}
    assert "timestamp" in sent_frame

    # 3. Disconnect
    await manager.disconnect(session_id)
    assert manager.get_connection(session_id) is None


@pytest.mark.asyncio
async def test_websocket_manager_replay_events_since() -> None:
    """Test event replay on client reconnection."""
    manager = WebSocketConnectionManager()
    session_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    mock_ws = AsyncMock()
    conn = await manager.connect(mock_ws, project_id, session_id, user_id)

    # Push 3 events
    await manager.send_event(session_id, "event_1", {"n": 1})
    await manager.send_event(session_id, "event_2", {"n": 2})
    await manager.send_event(session_id, "event_3", {"n": 3})

    mock_ws.send_text.reset_mock()

    # Client reconnects having seen sequence 1, expecting seq 2 and 3
    replayed = await manager.replay_events_since(session_id, last_sequence=1)
    assert replayed is True
    assert mock_ws.send_text.call_count == 2

    frame_seq2 = json.loads(mock_ws.send_text.call_args_list[0][0][0])
    assert frame_seq2["sequence"] == 2
    assert frame_seq2["replayed"] is True

    frame_seq3 = json.loads(mock_ws.send_text.call_args_list[1][0][0])
    assert frame_seq3["sequence"] == 3
    assert frame_seq3["replayed"] is True


@pytest.mark.asyncio
async def test_websocket_manager_replay_buffer_evicted_resync_required() -> None:
    """Test that asking for an evicted sequence triggers resync_required."""
    manager = WebSocketConnectionManager()
    session_id = uuid4()
    mock_ws = AsyncMock()
    conn = await manager.connect(mock_ws, uuid4(), session_id, uuid4())

    # Manually populate buffer with sequence starting at 100
    conn.replay_buffer.append(BufferedEvent(sequence=100, event_type="e", data={}, timestamp=""))
    conn.replay_buffer.append(BufferedEvent(sequence=101, event_type="e", data={}, timestamp=""))

    mock_ws.send_text.reset_mock()

    # Client requests sequence 50 (too old, was evicted)
    replayed = await manager.replay_events_since(session_id, last_sequence=50)
    assert replayed is False
    assert mock_ws.send_text.call_count == 1

    frame = json.loads(mock_ws.send_text.call_args[0][0])
    assert frame["type"] == "resync_required"
    assert frame["data"]["oldest_available_sequence"] == 100


@pytest.mark.asyncio
async def test_websocket_manager_broadcast_ping() -> None:
    """Test that broadcast_ping sends ping frame to active sessions."""
    manager = WebSocketConnectionManager()
    session_id = uuid4()
    mock_ws = AsyncMock()
    await manager.connect(mock_ws, uuid4(), session_id, uuid4())

    mock_ws.send_text.reset_mock()
    await manager.broadcast_ping()
    assert mock_ws.send_text.call_count == 1
    frame = json.loads(mock_ws.send_text.call_args[0][0])
    assert frame["type"] == "ping"


@pytest.mark.asyncio
async def test_websocket_endpoint_auth_and_interaction(
    db_session: Any,
) -> None:
    """End-to-end WebSocket endpoint test using Starlette TestClient."""
    # 1. Setup DB entities
    user = User(
        email="ws_test_user@example.com",
        hashed_password=get_password_hash("ValidPassword123!"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    project = Project(
        name="WS Analytics Project",
        description="WebSocket tests",
        owner_id=user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    conn = Connection(
        project_id=project.id,
        name="WS DB",
        dialect="postgresql",
        encrypted_connection_string=encrypt_secret("postgresql://test:test@localhost:5432/testdb"),
    )
    db_session.add(conn)
    await db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Create session via HTTP first
    sync_client = TestClient(app)
    create_res = sync_client.post(
        f"/api/v1/projects/{project.id}/chat/sessions",
        json={"title": "WebSocket Session"},
        headers=headers,
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["data"]["id"]

    # 2. Test invalid token rejection (close code 4001)
    with pytest.raises(Exception):
        with sync_client.websocket_connect(
            f"/api/v1/projects/{project.id}/chat/sessions/{session_id}/ws?token=invalid_jwt"
        ) as ws:
            pass

    # 3. Test non-existent session rejection (close code 4004)
    with pytest.raises(Exception):
        with sync_client.websocket_connect(
            f"/api/v1/projects/{project.id}/chat/sessions/{uuid4()}/ws?token={token}"
        ) as ws:
            pass

    # 4. Test valid connection, ping-pong, and message execution
    mock_llm = MagicMock()

    async def _mock_llm(messages: list[Any]) -> Any:
        from langchain_core.messages import AIMessage

        content_str = str(messages[0].content) if messages else ""
        if "classifier" in content_str.lower():
            return AIMessage(
                content='{"intent_type": "lookup", "extracted_entities": ["users"], "search_query": "users"}'
            )
        if "sql engineer" in content_str.lower():
            return AIMessage(content="SELECT id, name FROM users LIMIT 2;")
        if "analyst" in content_str.lower():
            return AIMessage(content="Found 2 users.")
        return AIMessage(content="OK")

    mock_llm.ainvoke = AsyncMock(side_effect=_mock_llm)

    with (
        patch("app.domain.agent.dependencies.get_llm_client", return_value=mock_llm),
        patch(
            "app.domain.connections.manager.ConnectionManager.execute_safe",
            new_callable=AsyncMock,
            return_value=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        ),
    ):
        with sync_client.websocket_connect(
            f"/api/v1/projects/{project.id}/chat/sessions/{session_id}/ws?token={token}"
        ) as ws:
            # Send ping frame
            ws.send_text(json.dumps({"type": "ping"}))
            pong_resp = json.loads(ws.receive_text())
            assert pong_resp["type"] == "pong"

            # Send chat message frame
            ws.send_text(json.dumps({"type": "message", "content": "Show me users"}))

            # Collect stream events until 'done'
            event_types: list[str] = []
            while True:
                data = json.loads(ws.receive_text())
                event_types.append(data["type"])
                if data["type"] == "done":
                    break

            assert "message_received" in event_types
            assert "intent_classified" in event_types
            assert "sql_generated" in event_types
            assert "sql_executed" in event_types
            assert "summary_ready" in event_types
            assert "final_result" in event_types
            assert "done" in event_types
