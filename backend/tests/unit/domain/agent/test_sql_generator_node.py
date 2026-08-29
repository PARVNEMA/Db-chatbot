"""
Unit tests for SQL Generator node (Phase 5).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.sql_generator import create_sql_generator_node
from app.domain.agent.state import AgentState


@pytest.mark.asyncio
async def test_sql_generator_initial_generation() -> None:
    """Test initial SQL generation without error history."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="```sql\nSELECT id, name FROM users LIMIT 10;\n```")
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
        "user_query": "List first 10 users",
        "intent_type": "lookup",
        "extracted_entities": ["users"],
        "relevant_schema": {},
        "schema_context": "Table: users (id, name)",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    generator_fn = create_sql_generator_node(mock_deps)
    result = await generator_fn(state)

    assert result["generated_sql"] == "SELECT id, name FROM users LIMIT 10;"
    assert result["sql_dialect"] == "postgresql"


@pytest.mark.asyncio
async def test_sql_generator_self_correction_on_retry() -> None:
    """Test SQL generator uses correction prompt when execution_error is present."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="SELECT id, full_name FROM users LIMIT 10;")
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
        "user_query": "List first 10 users",
        "intent_type": "lookup",
        "extracted_entities": ["users"],
        "relevant_schema": {},
        "schema_context": "Table: users (id, full_name)",
        "generated_sql": "SELECT id, name FROM users LIMIT 10;",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": "column 'name' does not exist",
        "retry_count": 1,
        "error_history": ["Attempt 1: column 'name' does not exist"],
        "nl_summary": "",
        "messages": [],
    }

    generator_fn = create_sql_generator_node(mock_deps)
    result = await generator_fn(state)

    assert result["generated_sql"] == "SELECT id, full_name FROM users LIMIT 10;"
