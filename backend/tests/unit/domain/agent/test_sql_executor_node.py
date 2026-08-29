"""
Unit tests for SQL Executor node (Phase 6).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.sql_executor import create_sql_executor_node
from app.domain.agent.state import AgentState


@pytest.mark.asyncio
async def test_sql_executor_success() -> None:
    """Test successful SQL execution with valid SELECT query."""
    mock_connection_manager = MagicMock()
    mock_connection_manager.get_session = MagicMock()
    mock_connection_manager.execute_safe = AsyncMock(
        return_value=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    )

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_connection_manager,
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=MagicMock(),
        user_id=uuid.uuid4(),
    )

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "List users",
        "intent_type": "lookup",
        "extracted_entities": ["users"],
        "relevant_schema": {},
        "schema_context": "Table: users",
        "generated_sql": "SELECT id, name FROM users;",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    executor_fn = create_sql_executor_node(mock_deps)
    result = await executor_fn(state)

    assert result["execution_error"] is None
    assert len(result["execution_result"]) == 2
    assert result["execution_result"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_sql_executor_rejects_dml() -> None:
    """Test SQL executor blocks forbidden DML before database execution."""
    mock_connection_manager = MagicMock()
    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_connection_manager,
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=MagicMock(),
        user_id=uuid.uuid4(),
    )

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Delete all users",
        "intent_type": "lookup",
        "extracted_entities": ["users"],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "DELETE FROM users WHERE id = 1;",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    executor_fn = create_sql_executor_node(mock_deps)
    result = await executor_fn(state)

    assert result["execution_result"] == []
    assert result["execution_error"] is not None
    assert result["retry_count"] == 1
    assert len(result["error_history"]) == 1


@pytest.mark.asyncio
async def test_sql_executor_database_runtime_error() -> None:
    """Test SQL executor records database runtime error for self-correction."""
    mock_connection_manager = MagicMock()
    mock_connection_manager.get_session = MagicMock()
    mock_connection_manager.execute_safe = AsyncMock(
        side_effect=Exception("relation 'customers' does not exist")
    )

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_connection_manager,
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=MagicMock(),
        user_id=uuid.uuid4(),
    )

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "List customers",
        "intent_type": "lookup",
        "extracted_entities": ["customers"],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "SELECT * FROM customers;",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    executor_fn = create_sql_executor_node(mock_deps)
    result = await executor_fn(state)

    assert result["execution_result"] == []
    assert "relation 'customers' does not exist" in result["execution_error"]
    assert result["retry_count"] == 1
