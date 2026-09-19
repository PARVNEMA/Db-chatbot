"""Unit tests for Phase 5 Interactive HITL Collection and WebSocket Approval Protocol."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.missing_field_collector import (
    create_missing_field_collector_node,
    find_missing_required_fields,
)
from app.domain.agent.nodes.mutation_previewer import (
    compute_change_set_hash,
    create_mutation_previewer_node,
)
from app.domain.agent.state import AgentState
from app.domain.chat.models import ChatSession, PendingMutation
from app.domain.chat.services import ChatService
from app.domain.connections.models import Connection
from app.domain.projects.models import Project
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
                column_name="code",
                data_type="varchar(10)",
                is_nullable=False,  # Required!
                is_primary_key=False,
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
                is_nullable=False,  # Required!
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=2,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_id,
                column_name="email",
                data_type="varchar(100)",
                is_nullable=False,  # Required!
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=3,
                created_at=now,
            ),
            ColumnResponse(
                id=uuid.uuid4(),
                table_id=emp_id,
                column_name="created_at",
                data_type="timestamp",
                is_nullable=False,
                column_default="CURRENT_TIMESTAMP",  # Has default -> not missing
                is_primary_key=False,
                is_read_only=False,
                ordinal_position=4,
                created_at=now,
            ),
        ],
        created_at=now,
    )

    return [dept_table, emp_table]


# ==============================================================================
# 1. Missing Field Collector Tests (Single-Turn Collection)
# ==============================================================================


def test_find_missing_required_fields_collects_all_in_one_go() -> None:
    """Verify that all missing required fields across all tables and rows are collected in one go."""
    tables = _make_sample_tables()

    # Change-set missing 'code' on departments and 'email' on employees
    change_set = {
        "summary": "Add department and employee",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Sales"}],  # Missing 'code'
            },
            {
                "sequence": 2,
                "operation": "insert",
                "table": "employees",
                "columns": ["name"],
                "rows": [{"name": "Alice"}],  # Missing 'email'
            },
        ],
    }

    missing = find_missing_required_fields(change_set, tables)

    # Both missing fields identified simultaneously
    assert len(missing) == 2
    missing_keys = {m["field_key"] for m in missing}
    assert "departments[0].code" in missing_keys
    assert "employees[0].email" in missing_keys


def test_find_missing_required_fields_none_missing() -> None:
    """Verify that complete proposals return an empty list."""
    tables = _make_sample_tables()

    change_set = {
        "summary": "Add department and employee",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name", "code"],
                "rows": [{"name": "Sales", "code": "SLS"}],
            },
            {
                "sequence": 2,
                "operation": "insert",
                "table": "employees",
                "columns": ["name", "email"],
                "rows": [{"name": "Alice", "email": "alice@co.com"}],
            },
        ],
    }

    missing = find_missing_required_fields(change_set, tables)
    assert len(missing) == 0


@pytest.mark.asyncio
async def test_missing_field_collector_node_emits_single_socket_frame() -> None:
    """Verify that node sends one mutation_field_required event with all missing fields."""
    tables = _make_sample_tables()
    mock_schema = MagicMock()
    mock_schema.list_tables = AsyncMock(return_value=tables)

    mock_ws = MagicMock()
    mock_ws.send_event = AsyncMock()

    deps = MagicMock(spec=GraphDependencies)
    deps.schema_service = mock_schema
    deps.ws_manager = mock_ws
    deps.user_id = uuid.uuid4()

    node = create_missing_field_collector_node(deps)

    change_set = {
        "summary": "Add department",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name"],
                "rows": [{"name": "Finance"}],  # Missing 'code'
            }
        ],
    }

    session_id = uuid.uuid4()
    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": session_id,
        "connection_id": uuid.uuid4(),
        "user_query": "Add finance dept",
        "intent_type": "insert",
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
        "mutation_change_set": change_set,
    }

    result = await node(state)
    assert result["mutation_status"] == "COLLECTING_INPUT"
    assert "departments[0].code" in result["mutation_fields_pending"]

    # Verify single WebSocket frame was broadcast with missing_fields
    mock_ws.send_event.assert_called_once()
    call_args = mock_ws.send_event.call_args
    event_type = call_args.kwargs.get("event_type") or call_args.args[1]
    event_data = call_args.kwargs.get("data") or call_args.args[2]
    assert event_type == "mutation_field_required"
    assert len(event_data["missing_fields"]) == 1
    assert event_data["missing_fields"][0]["column"] == "code"


# ==============================================================================
# 2. Mutation Previewer & Hash Tests
# ==============================================================================


def test_compute_change_set_hash_deterministic() -> None:
    """Verify change-set hash is deterministic across key ordering."""
    cs1 = {"summary": "A", "mutations": [{"sequence": 1, "table": "t1"}]}
    cs2 = {"mutations": [{"sequence": 1, "table": "t1"}], "summary": "A"}

    h1 = compute_change_set_hash(cs1)
    h2 = compute_change_set_hash(cs2)
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_mutation_previewer_node_stages_and_emits_frames() -> None:
    """Verify node persists PendingMutation and broadcasts preview frames."""
    conn = MagicMock(spec=Connection)
    conn.id = uuid.uuid4()
    conn.max_patch_rows_per_table = 5
    conn.approval_timeout_minutes = 20

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_ws = MagicMock()
    mock_ws.send_event = AsyncMock()

    deps = MagicMock(spec=GraphDependencies)
    deps.db = mock_db
    deps.connection = conn
    deps.connection_manager = None
    deps.ws_manager = mock_ws
    deps.user_id = uuid.uuid4()

    node = create_mutation_previewer_node(deps)

    change_set = {
        "summary": "Insert department",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "columns": ["name", "code"],
                "rows": [{"name": "HR", "code": "HR01"}],
            }
        ],
    }

    session_id = uuid.uuid4()
    project_id = uuid.uuid4()
    state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": conn.id,
        "user_query": "Add HR",
        "intent_type": "insert",
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
        "mutation_change_set": change_set,
    }

    result = await node(state)
    assert result["mutation_status"] == "PENDING_APPROVAL"
    assert result["mutation_id"] is not None

    # Verify both mutation_preview and mutation_approval_required frames were sent
    assert mock_ws.send_event.call_count == 2
    sent_event_types = [
        call.kwargs.get("event_type") or call.args[1]
        for call in mock_ws.send_event.call_args_list
    ]
    assert "mutation_preview" in sent_event_types
    assert "mutation_approval_required" in sent_event_types


# ==============================================================================
# 3. ChatService Approval & Rejection Handlers Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_approve_mutation_success() -> None:
    """Project owner can approve a pending mutation."""
    owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id

    mock_session = MagicMock(spec=ChatSession)
    mock_session.id = session_id
    mock_session.project_id = project_id

    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.session_id = session_id
    mock_mutation.project_id = project_id
    mock_mutation.status = "PENDING_APPROVAL"
    mock_mutation.expires_at = datetime.now(UTC) + timedelta(minutes=10)
    mock_mutation.approved_at = None

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    mock_conn_svc = MagicMock()
    mock_ws = MagicMock()
    mock_ws.send_event = AsyncMock()

    mock_db = MagicMock()

    service = ChatService(
        db=mock_db,
        project_service=mock_proj_svc,
        connection_service=mock_conn_svc,
        ws_manager=mock_ws,
    )
    service.get_session = AsyncMock(return_value=mock_session)
    service._mutation_repo.get_by_id_and_project = AsyncMock(return_value=mock_mutation)
    service._mutation_repo.get_by_idempotency_key = AsyncMock(return_value=None)
    service._mutation_repo.update_status = AsyncMock(return_value=mock_mutation)

    res = await service.approve_mutation(
        project_id=project_id,
        session_id=session_id,
        mutation_id=mutation_id,
        user_id=owner_id,
        idempotency_key="key-12345",
    )

    assert res == mock_mutation
    service._mutation_repo.update_status.assert_called_once_with(
        mutation=mock_mutation,
        status="APPROVED",
        approver_id=owner_id,
    )
    mock_ws.send_event.assert_called_once()
    assert (mock_ws.send_event.call_args.kwargs.get("event_type") or mock_ws.send_event.call_args.args[1]) == "mutation_approved"


@pytest.mark.asyncio
async def test_approve_mutation_forbidden_for_non_owner() -> None:
    """Non-owner user is forbidden from approving mutations."""
    owner_id = uuid.uuid4()
    non_owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id  # Owner is different

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    service = ChatService(
        db=MagicMock(),
        project_service=mock_proj_svc,
        connection_service=MagicMock(),
    )

    with pytest.raises(ForbiddenException, match="Only the project owner"):
        await service.approve_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=non_owner_id,
            idempotency_key="key-1",
        )


@pytest.mark.asyncio
async def test_approve_mutation_expired_raises_error() -> None:
    """Expired mutation cannot be approved."""
    owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id

    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.session_id = session_id
    mock_mutation.project_id = project_id
    mock_mutation.status = "PENDING_APPROVAL"
    mock_mutation.expires_at = datetime.now(UTC) - timedelta(minutes=5)  # Already expired

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    service = ChatService(
        db=MagicMock(),
        project_service=mock_proj_svc,
        connection_service=MagicMock(),
    )
    service.get_session = AsyncMock()
    service._mutation_repo.get_by_id_and_project = AsyncMock(return_value=mock_mutation)
    service._mutation_repo.update_status = AsyncMock()

    with pytest.raises(BadRequestException, match="expired"):
        await service.approve_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
            idempotency_key="key-1",
        )

    service._mutation_repo.update_status.assert_called_once_with(mock_mutation, status="EXPIRED")


@pytest.mark.asyncio
async def test_reject_mutation_success() -> None:
    """Project owner can reject a pending mutation."""
    owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id

    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.session_id = session_id
    mock_mutation.project_id = project_id
    mock_mutation.status = "PENDING_APPROVAL"

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)
    mock_ws = MagicMock()
    mock_ws.send_event = AsyncMock()

    service = ChatService(
        db=MagicMock(),
        project_service=mock_proj_svc,
        connection_service=MagicMock(),
        ws_manager=mock_ws,
    )
    service.get_session = AsyncMock()
    service._mutation_repo.get_by_id_and_project = AsyncMock(return_value=mock_mutation)
    service._mutation_repo.update_status = AsyncMock(return_value=mock_mutation)

    res = await service.reject_mutation(
        project_id=project_id,
        session_id=session_id,
        mutation_id=mutation_id,
        user_id=owner_id,
        reason="Budget too high",
    )

    assert res == mock_mutation
    service._mutation_repo.update_status.assert_called_once_with(
        mutation=mock_mutation,
        status="REJECTED",
        approver_id=owner_id,
    )
    mock_ws.send_event.assert_called_once()
    assert (mock_ws.send_event.call_args.kwargs.get("event_type") or mock_ws.send_event.call_args.args[1]) == "mutation_rejected"
