"""
Unit tests for full LangGraph Agent Workflow and Self-Correction Loop (Phase 8).
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.graph import (
    build_agent_graph,
    route_after_execution,
    route_after_intent,
)
from app.domain.agent.state import AgentState
from app.domain.embeddings.schemas import SchemaSearchResult


def test_route_after_intent() -> None:
    """Test routing based on classified intent."""
    state_general: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Hello, who are you?",
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
    assert route_after_intent(state_general) == "general_chat"

    state_db_query: AgentState = {**state_general, "intent_type": "lookup"}
    assert route_after_intent(state_db_query) == "sql_generator"


def test_route_after_execution() -> None:
    """Test conditional router logic for all state conditions."""
    # 1. Success -> result_formatter
    state_success: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "q",
        "intent_type": "lookup",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "SELECT 1;",
        "sql_dialect": "postgresql",
        "execution_result": [{"1": 1}],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }
    assert route_after_execution(state_success) == "result_formatter"

    # 2. Error with retry_count < 3 -> sql_generator
    state_retry: AgentState = {**state_success, "execution_error": "Syntax error", "retry_count": 1}
    assert route_after_execution(state_retry) == "sql_generator"

    # 3. Error with retry_count >= 3 -> error_terminal
    state_exhausted: AgentState = {**state_success, "execution_error": "Fatal error", "retry_count": 3}
    assert route_after_execution(state_exhausted) == "error_terminal"


@pytest.mark.asyncio
async def test_full_graph_general_conversation_flow() -> None:
    """Test that general conversational input is handled directly by general_chat node without SQL generation."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_llm = MagicMock()

    async def _mock_llm_ainvoke(messages: list[Any]) -> AIMessage:
        content_str = str(messages[0].content) if messages else ""
        if "classifier" in content_str.lower():
            return AIMessage(
                content='{"intent_type": "general", "extracted_entities": [], "search_query": "hello"}'
            )
        # General conversation node
        return AIMessage(
            content="Hello! I am your AI database assistant. How can I help you query your data today?"
        )

    mock_llm.ainvoke = AsyncMock(side_effect=_mock_llm_ainvoke)

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=mock_llm,
        user_id=user_id,
    )

    graph = build_agent_graph(mock_deps)

    initial_state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "Hello there!",
        "intent_type": "",
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

    final_state = await graph.ainvoke(initial_state)

    assert final_state["intent_type"] == "general"
    assert final_state["generated_sql"] == ""
    assert final_state["execution_result"] == []
    assert (
        final_state["nl_summary"]
        == "I can help with database-related questions. Please ask about querying or analyzing your data."
    )
    assert mock_llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_full_graph_success_flow() -> None:
    """Test executing the full graph on the happy path for database queries."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_llm = MagicMock()

    async def _mock_llm_ainvoke(messages: list[Any]) -> AIMessage:
        content_str = str(messages[0].content) if messages else ""
        if "classifier" in content_str.lower():
            return AIMessage(
                content='{"intent_type": "lookup", "extracted_entities": ["users"], "search_query": "users"}'
            )
        if "sql engineer" in content_str.lower():
            return AIMessage(content="SELECT id, name FROM users LIMIT 5;")
        if "analyst" in content_str.lower():
            return AIMessage(content="Found 2 users: Alice and Bob.")
        return AIMessage(content="OK")

    mock_llm.ainvoke = AsyncMock(side_effect=_mock_llm_ainvoke)

    # Mock embedding search
    mock_embedding_service = MagicMock()
    mock_search_result = SchemaSearchResult(
        column_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
        table_name="users",
        column_name="name",
        data_type="TEXT",
        is_primary_key=False,
        is_foreign_key=False,
        embed_text="users.name",
        similarity_score=0.9,
    )
    mock_embedding_service.search_schema = AsyncMock(return_value=[mock_search_result])

    # Mock connection manager
    mock_conn_mgr = MagicMock()
    mock_conn_mgr.get_session = MagicMock()
    mock_conn_mgr.execute_safe = AsyncMock(
        return_value=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    )

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_conn_mgr,
        embedding_service=mock_embedding_service,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=mock_llm,
        user_id=user_id,
    )

    graph = build_agent_graph(mock_deps)

    initial_state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "Show me the users",
        "intent_type": "",
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

    final_state = await graph.ainvoke(initial_state)

    assert final_state["intent_type"] == "lookup"
    assert "SELECT id, name FROM users LIMIT 5;" in final_state["generated_sql"]
    assert len(final_state["execution_result"]) == 2
    assert final_state["execution_error"] is None
    assert "Found 2 users" in final_state["nl_summary"]


@pytest.mark.asyncio
async def test_full_graph_self_correction_flow() -> None:
    """Test graph automatically self-corrects on initial SQL execution error."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    attempt = 0

    async def _mock_llm_ainvoke(messages: list[Any]) -> AIMessage:
        nonlocal attempt
        content_str = str(messages[0].content) if messages else ""
        if "classifier" in content_str.lower():
            return AIMessage(
                content='{"intent_type": "lookup", "extracted_entities": ["users"], "search_query": "users"}'
            )
        if "sql engineer" in content_str.lower():
            # First attempt produces bad SQL
            return AIMessage(content="SELECT invalid_col FROM users;")
        if "debugger" in content_str.lower():
            # Second attempt produces fixed SQL
            return AIMessage(content="SELECT id, name FROM users;")
        if "analyst" in content_str.lower():
            return AIMessage(content="Fixed query and retrieved users.")
        return AIMessage(content="OK")

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=_mock_llm_ainvoke)

    # Mock embedding search
    mock_embedding_service = MagicMock()
    mock_embedding_service.search_schema = AsyncMock(return_value=[])

    # Mock connection manager: fail on first execute_safe call, succeed on second
    mock_conn_mgr = MagicMock()
    mock_conn_mgr.get_session = MagicMock()

    execute_count = 0

    async def _mock_execute_safe(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal execute_count
        execute_count += 1
        if execute_count == 1:
            raise Exception("column 'invalid_col' does not exist")
        return [{"id": 1, "name": "Alice"}]

    mock_conn_mgr.execute_safe = AsyncMock(side_effect=_mock_execute_safe)

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_conn_mgr,
        embedding_service=mock_embedding_service,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(dialect="postgresql", encrypted_connection_string="enc_str"),
        llm=mock_llm,
        user_id=user_id,
    )

    graph = build_agent_graph(mock_deps)

    initial_state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "Show users",
        "intent_type": "",
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

    final_state = await graph.ainvoke(initial_state)

    # Self-correction succeeded on second attempt
    assert execute_count == 2
    assert final_state["retry_count"] == 1
    assert final_state["execution_error"] is None
    assert len(final_state["execution_result"]) == 1
    assert "Fixed query and retrieved users" in final_state["nl_summary"]
