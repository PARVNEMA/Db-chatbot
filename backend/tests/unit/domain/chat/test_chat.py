"""
Unit and API integration tests for Chat domain (Phases 9, 10, 11).

Tests:
- Chat session creation and connection association.
- Multi-tenant isolation for chat sessions.
- Session title update and deletion.
- Listing chat messages with pagination.
- Streaming SSE message response with mocked LLM and execution pipeline.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, encrypt_secret, get_password_hash
from app.domain.auth.models import User
from app.domain.connections.models import Connection
from app.domain.projects.models import Project


async def create_test_user_and_project(
    db: AsyncSession, email: str = "chat_user@example.com"
) -> tuple[User, Project, Connection, dict[str, str]]:
    """Helper to create a user, project, and connection."""
    user = User(
        email=email,
        hashed_password=get_password_hash("ValidPassword123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    project = Project(
        name="Test Analytics Project",
        description="For chat testing",
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    conn = Connection(
        project_id=project.id,
        name="Test DB",
        dialect="postgresql",
        encrypted_connection_string=encrypt_secret("postgresql://test:test@localhost:5432/testdb"),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    return user, project, conn, headers


@pytest.mark.asyncio
async def test_create_and_get_chat_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test creating a chat session and fetching it by ID."""
    _, project, _, headers = await create_test_user_and_project(
        db_session, email="session_test@example.com"
    )

    # 1. Create Session
    payload = {"title": "Sales Analysis Q1"}
    response = await client.post(
        f"/api/v1/projects/{project.id}/chat/sessions",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    session_id = body["data"]["id"]
    assert body["data"]["title"] == "Sales Analysis Q1"

    # 2. Get Session
    get_res = await client.get(
        f"/api/v1/projects/{project.id}/chat/sessions/{session_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    get_body = get_res.json()
    assert get_body["success"] is True
    assert get_body["data"]["id"] == session_id


@pytest.mark.asyncio
async def test_list_and_update_chat_sessions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test listing chat sessions and updating title."""
    _, project, _, headers = await create_test_user_and_project(
        db_session, email="list_test@example.com"
    )

    # Create 2 sessions
    await client.post(
        f"/api/v1/projects/{project.id}/chat/sessions",
        json={"title": "Session 1"},
        headers=headers,
    )
    res2 = await client.post(
        f"/api/v1/projects/{project.id}/chat/sessions",
        json={"title": "Session 2"},
        headers=headers,
    )
    session_2_id = res2.json()["data"]["id"]

    # List sessions
    list_res = await client.get(
        f"/api/v1/projects/{project.id}/chat/sessions?skip=0&limit=10",
        headers=headers,
    )
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert list_body["data"]["total"] >= 2

    # Patch title
    patch_res = await client.patch(
        f"/api/v1/projects/{project.id}/chat/sessions/{session_2_id}",
        json={"title": "Updated Session 2"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["title"] == "Updated Session 2"

    # Delete session
    del_res = await client.delete(
        f"/api/v1/projects/{project.id}/chat/sessions/{session_2_id}",
        headers=headers,
    )
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_chat_session_cross_user_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test User B cannot access User A's chat sessions."""
    _, project_a, _, headers_a = await create_test_user_and_project(
        db_session, email="user_a@example.com"
    )
    _, _, _, headers_b = await create_test_user_and_project(
        db_session, email="user_b@example.com"
    )

    # User A creates a session
    create_res = await client.post(
        f"/api/v1/projects/{project_a.id}/chat/sessions",
        json={"title": "Private Session A"},
        headers=headers_a,
    )
    session_a_id = create_res.json()["data"]["id"]

    # User B attempts to access User A's session -> 404
    get_res = await client.get(
        f"/api/v1/projects/{project_a.id}/chat/sessions/{session_a_id}",
        headers=headers_b,
    )
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_send_chat_message_streaming(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test sending a message and receiving SSE stream chunks."""
    _, project, _, headers = await create_test_user_and_project(
        db_session, email="stream_user@example.com"
    )

    # 1. Create a session
    sess_res = await client.post(
        f"/api/v1/projects/{project.id}/chat/sessions",
        json={"title": "Streaming Test"},
        headers=headers,
    )
    session_id = sess_res.json()["data"]["id"]

    # 2. Mock LLM calls & ConnectionManager execution
    mock_llm = MagicMock()

    async def _mock_llm(messages: list[Any]) -> AIMessage:
        content_str = str(messages[0].content) if messages else ""
        if "classifier" in content_str.lower():
            return AIMessage(
                content='{"intent_type": "lookup", "extracted_entities": ["users"], "search_query": "users"}'
            )
        if "sql engineer" in content_str.lower():
            return AIMessage(content="SELECT id, name FROM users LIMIT 5;")
        if "analyst" in content_str.lower():
            return AIMessage(content="Here are the 2 users found.")
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
        # 3. Post chat message to SSE stream endpoint
        response = await client.post(
            f"/api/v1/projects/{project.id}/chat/sessions/{session_id}/messages",
            json={"content": "Show me the top 5 users"},
            headers=headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        stream_content = response.text
        assert "event: message_received" in stream_content
        assert "event: intent_classified" in stream_content
        assert "event: sql_generated" in stream_content
        assert "event: sql_executed" in stream_content
        assert "event: summary_ready" in stream_content
        assert "event: final_result" in stream_content
        assert "event: done" in stream_content

    # 4. Verify message history was persisted
    history_res = await client.get(
        f"/api/v1/projects/{project.id}/chat/sessions/{session_id}/messages",
        headers=headers,
    )
    assert history_res.status_code == 200
    msgs = history_res.json()["data"]["items"]
    assert len(msgs) >= 2  # user message and assistant message
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["selected_query_run"] is not None
    assert msgs[1]["selected_query_run"]["status"] == "success"
