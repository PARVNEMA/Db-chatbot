"""Unit tests for Phase 4 Mutation Planner Node and Writable Schema Formatting."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.graph import build_agent_graph
from app.domain.agent.nodes.mutation_planner import (
    create_mutation_planner_node,
    format_writable_schema_context,
)
from app.domain.agent.prompts import parse_mutation_planner_response
from app.domain.agent.state import AgentState
from app.domain.connections.models import Connection
from app.domain.schema_introspection.schemas import (
    ColumnResponse,
    TableDetailResponse,
)


def _make_sample_tables() -> list[TableDetailResponse]:
    """Create sample schema tables with PK, FK, defaults, and read-only annotations."""
    now = datetime.now(UTC)
    dept_id = uuid.uuid4()
    emp_id = uuid.uuid4()

    dept_table = TableDetailResponse(
        id=dept_id,
        connection_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        schema_name="public",
        table_name="departments",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_id,
                column_name="id",
                data_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_read_only=True,
                ordinal_position=1,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_id,
                column_name="name",
                data_type="varchar(100)",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=2,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_id,
                column_name="created_at",
                data_type="timestamp",
                is_nullable=False,
                column_default="CURRENT_TIMESTAMP",
                is_read_only=False,
                ordinal_position=3,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    emp_table = TableDetailResponse(
        id=emp_id,
        connection_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        schema_name="public",
        table_name="employees",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_id,
                column_name="id",
                data_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_read_only=True,
                ordinal_position=1,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_id,
                column_name="name",
                data_type="varchar(100)",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=2,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_id,
                column_name="department_id",
                data_type="integer",
                is_nullable=False,
                is_primary_key=False,
                is_foreign_key=True,
                fk_target_table="departments",
                fk_target_column="id",
                is_read_only=False,
                ordinal_position=3,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    return [dept_table, emp_table]


# ==============================================================================
# 1. Writable Schema Formatting Tests
# ==============================================================================


def test_format_writable_schema_context_annotations() -> None:
    """Verify schema formatting marks read-only, primary keys, required fields, and FKs."""
    tables = _make_sample_tables()
    _, text = format_writable_schema_context(tables)

    assert "Table: departments" in text
    assert "- id (integer) [PRIMARY KEY | READ-ONLY]" in text
    assert "- name (varchar(100)) [REQUIRED FOR INSERT]" in text
    # created_at has default, so NOT required for insert
    assert "- created_at (timestamp)" in text
    assert "REQUIRED FOR INSERT" not in text.split("created_at")[1].split("\n")[0]
    # employees FK
    assert "REFERENCES departments.id" in text


def test_format_writable_schema_context_excludes_blocked_tables() -> None:
    """Verify blocked tables are omitted from writable schema context."""
    tables = _make_sample_tables()
    _, text = format_writable_schema_context(tables, blocked_tables=["departments"])

    assert "Table: departments" not in text
    assert "Table: employees" in text


# ==============================================================================
# 2. Mutation Planner Response Parser Tests
# ==============================================================================


def test_parse_mutation_planner_response_valid_json() -> None:
    """Test parsing clean JSON response."""
    payload = {
        "summary": "Insert department",
        "expected_total_rows_affected": 1,
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Sales"}],
            }
        ],
    }
    raw = f"```json\n{json.dumps(payload)}\n```"
    parsed = parse_mutation_planner_response(raw)
    assert parsed["summary"] == "Insert department"
    assert len(parsed["mutations"]) == 1


def test_parse_mutation_planner_response_invalid_json() -> None:
    """Test parsing invalid JSON raises ValueError."""
    with pytest.raises(ValueError, match="Could not parse valid mutation proposal"):
        parse_mutation_planner_response("Sorry, I can't generate a JSON proposal.")


# ==============================================================================
# 3. Mutation Planner Node Execution Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mutation_planner_node_refuses_when_writes_disabled() -> None:
    """Planner node immediately returns refusal when connection writes_enabled is False."""
    conn = MagicMock(spec=Connection)
    conn.writes_enabled = False
    conn.dialect = "postgresql"
    conn.blocked_tables = []

    deps = MagicMock(spec=GraphDependencies)
    deps.connection = conn

    node = create_mutation_planner_node(deps)

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Add a new department named Logistics",
        "intent_type": "insert",
        "extracted_entities": ["departments"],
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

    result = await node(state)
    assert result["mutation_status"] == "writes_disabled"
    assert "disabled" in result["nl_summary"].lower()
    assert result["mutation_change_set"] is None


@pytest.mark.asyncio
async def test_mutation_planner_node_generates_valid_proposal() -> None:
    """Planner node successfully constructs structured proposal when writes are enabled."""
    conn = MagicMock(spec=Connection)
    conn.writes_enabled = True
    conn.dialect = "postgresql"
    conn.blocked_tables = []

    tables = _make_sample_tables()
    mock_schema_service = MagicMock()
    mock_schema_service.list_tables = AsyncMock(return_value=tables)

    llm_output = {
        "summary": "Create department Engineering",
        "expected_total_rows_affected": 1,
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Engineering"}],
                "dependencies": [],
            }
        ],
    }

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=json.dumps(llm_output)))

    deps = MagicMock(spec=GraphDependencies)
    deps.connection = conn
    deps.schema_service = mock_schema_service
    deps.llm = mock_llm
    deps.user_id = uuid.uuid4()

    node = create_mutation_planner_node(deps)

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Add department Engineering",
        "intent_type": "insert",
        "extracted_entities": ["departments"],
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

    result = await node(state)
    assert result["mutation_status"] == "planned"
    assert result["mutation_change_set"] is not None
    assert result["mutation_change_set"]["summary"] == "Create department Engineering"
    assert result["mutation_change_set"]["mutations"][0]["table"] == "departments"


# ==============================================================================
# 4. End-to-End Write Path Workflow Test
# ==============================================================================


@pytest.mark.asyncio
async def test_agent_graph_write_path_flow() -> None:
    """Verify write query executes intent -> mutation_planner -> mutation_validator -> mutation_result_formatter."""
    conn = MagicMock(spec=Connection)
    conn.writes_enabled = True
    conn.dialect = "postgresql"
    conn.blocked_tables = []
    conn.max_tables_per_changeset = 3
    conn.max_total_rows_per_changeset = 10
    conn.max_insert_rows_per_table = 5
    conn.max_patch_rows_per_table = 5

    tables = _make_sample_tables()
    mock_schema_service = MagicMock()
    mock_schema_service.list_tables = AsyncMock(return_value=tables)

    # 1. Intent returns 'insert'
    intent_llm_output = '{"intent_type": "insert", "extracted_entities": ["departments"], "search_query": "departments"}'
    # 2. Planner returns valid proposal
    planner_llm_output = json.dumps(
        {
            "summary": "Create department Finance",
            "expected_total_rows_affected": 1,
            "mutations": [
                {
                    "sequence": 1,
                    "operation": "insert",
                    "table": "departments",
                    "columns": ["name"],
                    "rows": [{"name": "Finance"}],
                    "dependencies": [],
                }
            ],
        }
    )

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=intent_llm_output),
            AIMessage(content=planner_llm_output),
        ]
    )

    deps = MagicMock(spec=GraphDependencies)
    deps.connection = conn
    deps.schema_service = mock_schema_service
    deps.embedding_service = MagicMock()
    deps.embedding_service.search_schema = AsyncMock(return_value=[])
    deps.connection_manager = MagicMock()
    deps.connection_service = MagicMock()
    deps.project_service = MagicMock()
    deps.user_id = uuid.uuid4()
    deps.llm = mock_llm

    graph = build_agent_graph(deps)

    initial_state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Please add a new department named Finance",
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

    final_state = await graph.ainvoke(initial_state)

    # Verify state transitions and validation
    assert final_state["intent_type"] == "insert"
    assert final_state["mutation_status"] == "PENDING_APPROVAL"
    assert final_state["mutation_validation_error"] is None
    assert "Proposed Change-Set" in final_state["nl_summary"]
