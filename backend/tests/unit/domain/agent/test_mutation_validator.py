"""Unit tests for Phase 3 Deterministic Mutation Validator and Agent Node."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.mutation_schemas import (
    ChangeSetProposal,
    MutationItem,
)
from app.domain.agent.nodes.mutation_validator import (
    create_mutation_validator_node,
    validate_mutation_proposal,
)
from app.domain.agent.state import AgentState
from app.domain.connections.models import Connection
from app.domain.schema_introspection.schemas import (
    ColumnResponse,
    TableDetailResponse,
)


def _make_sample_connection(
    writes_enabled: bool = True,
    blocked_tables: list[str] | None = None,
    max_insert_rows_per_table: int = 5,
    max_patch_rows_per_table: int = 2,
    max_total_rows_per_changeset: int = 10,
    max_tables_per_changeset: int = 3,
) -> Connection:
    """Create a mock Connection instance with configurable write policy."""
    conn = MagicMock(spec=Connection)
    conn.id = uuid.uuid4()
    conn.project_id = uuid.uuid4()
    conn.dialect = "postgresql"
    conn.writes_enabled = writes_enabled
    conn.blocked_tables = blocked_tables or []
    conn.max_insert_rows_per_table = max_insert_rows_per_table
    conn.max_patch_rows_per_table = max_patch_rows_per_table
    conn.max_total_rows_per_changeset = max_total_rows_per_changeset
    conn.max_tables_per_changeset = max_tables_per_changeset
    return conn


def _make_sample_tables() -> list[TableDetailResponse]:
    """Create sample schema tables for testing."""
    now = datetime.now(UTC)
    dept_table_id = uuid.uuid4()
    emp_table_id = uuid.uuid4()
    log_table_id = uuid.uuid4()

    departments_table = TableDetailResponse(
        id=dept_table_id,
        connection_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        schema_name="public",
        table_name="departments",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_table_id,
                column_name="id",
                data_type="integer",
                is_nullable=False,
                is_primary_key=True,
                is_read_only=True,  # Identity / Serial
                ordinal_position=1,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_table_id,
                column_name="name",
                data_type="varchar",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=2,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=dept_table_id,
                column_name="budget",
                data_type="numeric",
                is_nullable=True,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=3,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    employees_table = TableDetailResponse(
        id=emp_table_id,
        connection_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        schema_name="public",
        table_name="employees",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_table_id,
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
                table_id=emp_table_id,
                column_name="name",
                data_type="varchar",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=2,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_table_id,
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
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_table_id,
                column_name="is_active",
                data_type="boolean",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=4,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    # Table without a primary key (e.g., event logs)
    logs_table = TableDetailResponse(
        id=log_table_id,
        connection_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        schema_name="public",
        table_name="logs",
        columns=[
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=log_table_id,
                column_name="message",
                data_type="text",
                is_nullable=False,
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=1,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    return [departments_table, employees_table, logs_table]


# ==============================================================================
# Unit Tests for validate_mutation_proposal
# ==============================================================================


@pytest.mark.asyncio
async def test_validate_mutation_writes_disabled() -> None:
    """Validator rejects all change-sets when connection writes_enabled is False."""
    conn = _make_sample_connection(writes_enabled=False)
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert department",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "HR"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "WRITES_DISABLED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_blocked_table() -> None:
    """Validator rejects mutations targeting tables in blocked_tables."""
    conn = _make_sample_connection(blocked_tables=["departments"])
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert department",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "HR"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "TABLE_BLOCKED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_table_not_found() -> None:
    """Validator rejects mutations targeting unknown tables."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert unknown",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="unknown_table",
                columns=["name"],
                rows=[{"name": "HR"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "TABLE_NOT_FOUND" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_max_tables_exceeded() -> None:
    """Validator rejects proposals that touch more tables than max_tables_per_changeset."""
    conn = _make_sample_connection(max_tables_per_changeset=1)
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert two tables",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "HR"}],
            ),
            MutationItem(
                sequence=2,
                operation="insert",
                table="employees",
                columns=["name", "department_id"],
                rows=[{"name": "Alice", "department_id": 1}],
            ),
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "MAX_TABLES_EXCEEDED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_max_total_rows_exceeded() -> None:
    """Validator rejects proposals exceeding total change-set row cap."""
    conn = _make_sample_connection(max_total_rows_per_changeset=2)
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert 3 rows total",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "HR"}, {"name": "Finance"}, {"name": "Legal"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "MAX_TOTAL_ROWS_EXCEEDED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_max_insert_rows_exceeded() -> None:
    """Validator rejects insert mutations exceeding per-table insert row cap."""
    conn = _make_sample_connection(max_insert_rows_per_table=2)
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert 3 rows",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "HR"}, {"name": "Finance"}, {"name": "Legal"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "MAX_INSERT_ROWS_EXCEEDED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_max_patch_rows_exceeded() -> None:
    """Validator rejects patch mutations exceeding per-table patch row cap."""
    conn = _make_sample_connection(max_patch_rows_per_table=1)
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Patch 2 rows",
        mutations=[
            MutationItem(
                sequence=1,
                operation="patch",
                table="departments",
                columns=["name"],
                rows=[
                    {"filter": {"id": 1}, "values": {"name": "HR New"}},
                    {"filter": {"id": 2}, "values": {"name": "Finance New"}},
                ],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "MAX_PATCH_ROWS_EXCEEDED" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_patch_table_no_pk() -> None:
    """Validator rejects PATCH targeting a table without a primary key."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Patch logs table",
        mutations=[
            MutationItem(
                sequence=1,
                operation="patch",
                table="logs",
                columns=["message"],
                filter={"message": "old log"},
                rows=[{"message": "new log"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "PATCH_TABLE_NO_PK" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_patch_missing_filter() -> None:
    """Validator rejects PATCH mutation with no filter/WHERE condition."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Unconstrained patch",
        mutations=[
            MutationItem(
                sequence=1,
                operation="patch",
                table="departments",
                columns=["name"],
                filter=None,
                rows=[{"name": "New Name"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "PATCH_MISSING_FILTER" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_read_only_column() -> None:
    """Validator rejects writes attempting to set is_read_only columns."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert specifying read-only id",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["id", "name"],
                rows=[{"id": 999, "name": "Engineering"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "READ_ONLY_COLUMN" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_column_not_found() -> None:
    """Validator rejects writes targeting non-existent columns."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Insert nonexistent column",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["nonexistent_col"],
                rows=[{"nonexistent_col": "val"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "COLUMN_NOT_FOUND" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_circular_dependency() -> None:
    """Validator rejects proposals with circular dependencies between mutations."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    # Mutation 0 depends on Mutation 1, Mutation 1 depends on Mutation 0
    proposal = ChangeSetProposal(
        summary="Circular reference",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name"],
                rows=[{"name": "Dept A"}],
                dependencies=[1],
            ),
            MutationItem(
                sequence=2,
                operation="insert",
                table="employees",
                columns=["name", "department_id"],
                rows=[{"name": "Bob", "department_id": "$ref:mutations[0].returning.id"}],
                dependencies=[0],
            ),
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "CIRCULAR_DEPENDENCY" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_ref_out_of_bounds() -> None:
    """Validator rejects $ref targeting nonexistent mutation index."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Out of bounds ref",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="employees",
                columns=["name", "department_id"],
                rows=[{"name": "Bob", "department_id": "$ref:mutations[99].returning.id"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "REF_TARGET_OUT_OF_BOUNDS" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_type_coercion_failure() -> None:
    """Validator rejects values that cannot be coerced to column data type."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Invalid integer format",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="employees",
                columns=["name", "department_id"],
                rows=[{"name": "Bob", "department_id": "not_an_integer"}],
            )
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert not result.is_valid
    assert any(e.code == "TYPE_COERCION_ERROR" for e in result.errors)


@pytest.mark.asyncio
async def test_validate_mutation_valid_multi_table_changeset() -> None:
    """Validator passes compliant multi-table proposal with $ref reference."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    proposal = ChangeSetProposal(
        summary="Add department and employee",
        mutations=[
            MutationItem(
                sequence=1,
                operation="insert",
                table="departments",
                columns=["name", "budget"],
                rows=[{"name": "Engineering", "budget": 100000.50}],
            ),
            MutationItem(
                sequence=2,
                operation="insert",
                table="employees",
                columns=["name", "department_id", "is_active"],
                rows=[
                    {
                        "name": "Alice",
                        "department_id": "$ref:mutations[0].returning.id",
                        "is_active": True,
                    }
                ],
                dependencies=[0],
            ),
        ],
    )

    result = await validate_mutation_proposal(proposal, conn, tables)
    assert result.is_valid
    assert len(result.errors) == 0
    assert result.total_rows == 2
    assert "departments" in result.table_names
    assert "employees" in result.table_names


# ==============================================================================
# Unit Tests for create_mutation_validator_node
# ==============================================================================


@pytest.mark.asyncio
async def test_mutation_validator_node_success() -> None:
    """Test LangGraph node successfully validates proposal in state."""
    conn = _make_sample_connection()
    tables = _make_sample_tables()

    mock_schema_service = MagicMock()
    mock_schema_service.list_tables = AsyncMock(return_value=tables)

    mock_deps = MagicMock(spec=GraphDependencies)
    mock_deps.connection = conn
    mock_deps.schema_service = mock_schema_service
    mock_deps.connection_manager = MagicMock()
    mock_deps.user_id = uuid.uuid4()

    node = create_mutation_validator_node(mock_deps)

    change_set = {
        "summary": "Add department",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Marketing"}],
            }
        ],
    }

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": conn.id,
        "user_query": "Add marketing dept",
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
        "mutation_change_set": change_set,
    }

    result = await node(state)
    assert result["mutation_status"] == "validated"
    assert result["mutation_validation_error"] is None


@pytest.mark.asyncio
async def test_mutation_validator_node_failure() -> None:
    """Test LangGraph node handles validation failure when writes_enabled is False."""
    conn = _make_sample_connection(writes_enabled=False)
    tables = _make_sample_tables()

    mock_schema_service = MagicMock()
    mock_schema_service.list_tables = AsyncMock(return_value=tables)

    mock_deps = MagicMock(spec=GraphDependencies)
    mock_deps.connection = conn
    mock_deps.schema_service = mock_schema_service
    mock_deps.connection_manager = MagicMock()
    mock_deps.user_id = uuid.uuid4()

    node = create_mutation_validator_node(mock_deps)

    change_set = {
        "summary": "Add department",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Marketing"}],
            }
        ],
    }

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": conn.id,
        "user_query": "Add marketing dept",
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
        "mutation_change_set": change_set,
    }

    result = await node(state)
    assert result["mutation_status"] == "validation_failed"
    assert "Write operations are disabled" in result["mutation_validation_error"]
