"""
Unit tests for Intent classification and schema linking node (Phase 4).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.intent import (
    create_intent_node,
    format_schema_context_from_results,
)
from app.domain.agent.state import AgentState
from app.domain.embeddings.schemas import SchemaSearchResult


def test_format_schema_context_from_results() -> None:
    """Test formatting vector search results into schema context."""
    results = [
        SchemaSearchResult(
            column_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            table_name="users",
            column_name="id",
            data_type="INTEGER",
            is_primary_key=True,
            is_foreign_key=False,
            embed_text="users.id",
            similarity_score=0.95,
        ),
        SchemaSearchResult(
            column_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
            table_name="orders",
            column_name="user_id",
            data_type="INTEGER",
            is_primary_key=False,
            is_foreign_key=True,
            fk_target_table="users",
            fk_target_column="id",
            embed_text="orders.user_id",
            similarity_score=0.88,
        ),
    ]

    schema_dict, prompt_str = format_schema_context_from_results(results)
    assert "users" in schema_dict
    assert "orders" in schema_dict
    assert "Table: users" in prompt_str
    assert "PRIMARY KEY" in prompt_str
    assert "REFERENCES users.id" in prompt_str


def test_format_schema_context_from_empty_results() -> None:
    """Test formatting when vector search returns no results."""
    schema_dict, prompt_str = format_schema_context_from_results([])
    assert schema_dict == {}
    assert prompt_str == ""


@pytest.mark.asyncio
async def test_intent_node_execution() -> None:
    """Test running intent node end-to-end with mocked dependencies."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Mock LLM response
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='{"intent_type": "aggregation", "extracted_entities": ["orders", "revenue"], "search_query": "orders revenue"}'
        )
    )

    # Mock EmbeddingService
    mock_embedding_service = MagicMock()
    mock_search_result = SchemaSearchResult(
        column_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
        table_name="orders",
        column_name="amount",
        data_type="NUMERIC",
        is_primary_key=False,
        is_foreign_key=False,
        embed_text="orders.amount",
        similarity_score=0.91,
    )
    mock_embedding_service.search_schema = AsyncMock(return_value=[mock_search_result])

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=mock_embedding_service,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(),
        llm=mock_llm,
        user_id=user_id,
    )

    state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "What is the total revenue from orders?",
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

    intent_node_fn = create_intent_node(mock_deps)
    result = await intent_node_fn(state)

    assert result["intent_type"] == "aggregation"
    assert "orders" in result["extracted_entities"]
    assert "orders" in result["relevant_schema"]
    assert "amount (NUMERIC)" in result["schema_context"]


@pytest.mark.asyncio
async def test_intent_node_empty_vector_results() -> None:
    """Test intent node behavior when vector search returns no results."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='{"intent_type": "lookup", "extracted_entities": ["something_unknown"], "search_query": "unknown"}'
        )
    )

    mock_embedding_service = MagicMock()
    mock_embedding_service.search_schema = AsyncMock(return_value=[])

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=mock_embedding_service,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(),
        llm=mock_llm,
        user_id=user_id,
    )

    state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "Find unknown data",
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

    intent_node_fn = create_intent_node(mock_deps)
    result = await intent_node_fn(state)

    assert result["intent_type"] == "lookup"
    assert result["extracted_entities"] == ["something_unknown"]
    assert result["relevant_schema"] == {}
    assert result["schema_context"] == ""
