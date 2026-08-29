"""
Unit tests for Result Formatter and Error Terminal nodes (Phase 7).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.error_terminal import error_terminal_node
from app.domain.agent.nodes.result_formatter import create_result_formatter_node
from app.domain.agent.state import AgentState


@pytest.mark.asyncio
async def test_result_formatter_node_success() -> None:
    """Test formatting successful query results into plain-English summary."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="There are 2 active users: Alice and Bob.")
    )

    mock_deps = GraphDependencies(
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
        "user_query": "How many active users are there?",
        "intent_type": "aggregation",
        "extracted_entities": ["users"],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "SELECT name FROM users WHERE active = true;",
        "sql_dialect": "postgresql",
        "execution_result": [{"name": "Alice"}, {"name": "Bob"}],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    formatter_fn = create_result_formatter_node(mock_deps)
    result = await formatter_fn(state)

    assert result["nl_summary"] == "There are 2 active users: Alice and Bob."


@pytest.mark.asyncio
async def test_error_terminal_node() -> None:
    """Test error terminal produces graceful explanation after exhausted retries."""
    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Show invalid metric",
        "intent_type": "lookup",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "SELECT non_existent FROM table;",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": "column 'non_existent' does not exist",
        "retry_count": 3,
        "error_history": [
            "Attempt 1: column 'non_existent' does not exist",
            "Attempt 2: column 'non_existent' does not exist",
            "Attempt 3: column 'non_existent' does not exist",
        ],
        "nl_summary": "",
        "messages": [],
    }

    result = await error_terminal_node(state)
    assert "unable to successfully execute a query" in result["nl_summary"]
    assert "column 'non_existent' does not exist" in result["nl_summary"]
