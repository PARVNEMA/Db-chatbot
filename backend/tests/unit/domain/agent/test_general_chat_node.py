"""Unit tests for the fixed general-chat response node."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.general_chat import create_general_chat_node
from app.domain.agent.state import AgentState


@pytest.mark.asyncio
async def test_general_chat_node_returns_database_redirect_without_calling_llm() -> None:
    """Return the fixed database-focused prompt without invoking the LLM."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock()
    deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql"),
        llm=mock_llm,
        user_id=uuid.uuid4(),
    )
    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Hello there!",
        "intent_type": "general",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    result = await create_general_chat_node(deps)(state)

    assert result == {
        "nl_summary": (
            "I can help with database-related questions. Please ask about querying "
            "or analyzing your data."
        ),
        "generated_sql": "",
        "execution_result": [],
        "execution_error": None,
    }
    mock_llm.ainvoke.assert_not_awaited()
