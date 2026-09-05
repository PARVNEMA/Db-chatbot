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
    expand_schema_tables,
    format_schema_context_from_results,
    format_schema_context_from_table_details,
)
from app.domain.agent.state import AgentState
from app.domain.embeddings.schemas import SchemaSearchResult
from app.domain.schema_introspection.schemas import ColumnResponse, TableDetailResponse


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


def test_expand_schema_tables_fk_outward_and_junction() -> None:
    """Test expand_schema_tables pulls in parent FK tables and junction tables."""
    now_dt = pytest.importorskip("datetime").datetime.now(pytest.importorskip("datetime").UTC)
    proj_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    # 1. Employees table
    emp_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=conn_id,
        project_id=proj_id,
        schema_name="public",
        table_name="employees",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="id",
                data_type="INTEGER",
                is_primary_key=True,
                is_foreign_key=False,
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="name",
                data_type="VARCHAR",
                is_primary_key=False,
                is_foreign_key=False,
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )

    # 2. Projects table
    proj_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=conn_id,
        project_id=proj_id,
        schema_name="public",
        table_name="projects",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="id",
                data_type="INTEGER",
                is_primary_key=True,
                is_foreign_key=False,
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="title",
                data_type="VARCHAR",
                is_primary_key=False,
                is_foreign_key=False,
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )

    # 3. Employee_projects junction table
    junction_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=conn_id,
        project_id=proj_id,
        schema_name="public",
        table_name="employee_projects",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="employee_id",
                data_type="INTEGER",
                is_primary_key=False,
                is_foreign_key=True,
                fk_target_table="employees",
                fk_target_column="id",
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="project_id",
                data_type="INTEGER",
                is_primary_key=False,
                is_foreign_key=True,
                fk_target_table="projects",
                fk_target_column="id",
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )

    all_tables = [emp_table, proj_table, junction_table]

    # Scenario A: Vector search only returns employee_projects.employee_id
    search_results = [
        SchemaSearchResult(
            column_id=uuid.uuid4(),
            table_id=junction_table.id,
            table_name="employee_projects",
            column_name="employee_id",
            data_type="INTEGER",
            is_primary_key=False,
            is_foreign_key=True,
            fk_target_table="employees",
            fk_target_column="id",
            embed_text="employee_projects.employee_id",
            similarity_score=0.9,
        )
    ]

    expanded = expand_schema_tables(
        search_results=search_results,
        all_tables=all_tables,
        extracted_entities=[],
    )
    table_names = {t.table_name for t in expanded}
    # Outward expansion should pull in both employees and projects from junction_table's FKs!
    assert "employee_projects" in table_names
    assert "employees" in table_names
    assert "projects" in table_names

    # Format check
    tables_map, schema_str = format_schema_context_from_table_details(expanded)
    assert "employee_projects" in tables_map
    assert "employees" in tables_map
    assert "projects" in tables_map
    assert "name (VARCHAR)" in schema_str
    assert "title (VARCHAR)" in schema_str
    assert "Relationships" in schema_str
    assert "employee_projects.employee_id -> employees.id" in schema_str


@pytest.mark.asyncio
async def test_intent_node_with_schema_service_fk_expansion() -> None:
    """Test intent node end-to-end when schema_service expands partial vector search results."""
    now_dt = pytest.importorskip("datetime").datetime.now(pytest.importorskip("datetime").UTC)
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='{"intent_type": "lookup", "extracted_entities": ["projects", "parv"], "search_query": "projects parv"}'
        )
    )

    # Vector search only returns employee_projects
    mock_embedding_service = MagicMock()
    mock_search_result = SchemaSearchResult(
        column_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
        table_name="employee_projects",
        column_name="employee_id",
        data_type="INTEGER",
        is_primary_key=False,
        is_foreign_key=True,
        fk_target_table="employees",
        fk_target_column="id",
        embed_text="employee_projects.employee_id",
        similarity_score=0.89,
    )
    mock_embedding_service.search_schema = AsyncMock(return_value=[mock_search_result])

    # Schema service returns all 3 tables
    emp_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=connection_id,
        project_id=project_id,
        table_name="employees",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="id",
                data_type="INTEGER",
                is_primary_key=True,
                is_foreign_key=False,
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="name",
                data_type="VARCHAR",
                is_primary_key=False,
                is_foreign_key=False,
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )
    proj_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=connection_id,
        project_id=project_id,
        table_name="projects",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="id",
                data_type="INTEGER",
                is_primary_key=True,
                is_foreign_key=False,
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="title",
                data_type="VARCHAR",
                is_primary_key=False,
                is_foreign_key=False,
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )
    ep_table = TableDetailResponse(
        id=uuid.uuid4(),
        connection_id=connection_id,
        project_id=project_id,
        table_name="employee_projects",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="employee_id",
                data_type="INTEGER",
                is_primary_key=False,
                is_foreign_key=True,
                fk_target_table="employees",
                fk_target_column="id",
                ordinal_position=1,
                created_at=now_dt,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=uuid.uuid4(),
                column_name="project_id",
                data_type="INTEGER",
                is_primary_key=False,
                is_foreign_key=True,
                fk_target_table="projects",
                fk_target_column="id",
                ordinal_position=2,
                created_at=now_dt,
            ),
        ],
        created_at=now_dt,
    )
    mock_schema_service = MagicMock()
    mock_schema_service.list_tables = AsyncMock(return_value=[emp_table, proj_table, ep_table])

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=mock_embedding_service,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        connection=MagicMock(),
        llm=mock_llm,
        user_id=user_id,
        schema_service=mock_schema_service,
    )

    state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "give me the projects in which parv is working",
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
    # All 3 tables must be present in relevant_schema and schema_context
    assert "employee_projects" in result["relevant_schema"]
    assert "employees" in result["relevant_schema"]
    assert "projects" in result["relevant_schema"]
    # The real employee column 'name' must be in the schema context
    assert "name (VARCHAR)" in result["schema_context"]
    assert "title (VARCHAR)" in result["schema_context"]
