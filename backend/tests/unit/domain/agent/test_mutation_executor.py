"""Unit tests for Phase 6: Transactional Execution Engine & Auditing."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.core.security import encrypt_secret
from app.domain.agent.nodes.mutation_executor import (
    ExecutionResult,
    execute_change_set,
    resolve_mutation_refs,
    resolve_ref_value,
    topological_sort_mutations,
)
from app.domain.agent.nodes.mutation_previewer import compute_change_set_hash
from app.domain.chat.models import ChatSession, PendingMutation
from app.domain.chat.services import ChatService
from app.domain.connections.models import Connection
from app.domain.projects.models import Project

# ==============================================================================
# 1. Topological Sorting & Cycle Detection Tests
# ==============================================================================


def test_topological_sort_independent_mutations() -> None:
    """Independent mutations retain their relative order."""
    mutations = [
        {"sequence": 1, "table": "users", "dependencies": []},
        {"sequence": 2, "table": "products", "dependencies": []},
    ]
    sorted_muts = topological_sort_mutations(mutations)
    assert len(sorted_muts) == 2
    assert [m["sequence"] for m in sorted_muts] == [1, 2]


def test_topological_sort_with_explicit_dependencies() -> None:
    """Child mutation depending on parent mutation is ordered after parent."""
    mutations = [
        {"sequence": 2, "table": "orders", "dependencies": [1]},
        {"sequence": 1, "table": "customers", "dependencies": []},
    ]
    sorted_muts = topological_sort_mutations(mutations)
    assert [m["sequence"] for m in sorted_muts] == [1, 2]


def test_topological_sort_with_implicit_ref_dependencies() -> None:
    """Child with $ref in row values is ordered after the referenced parent."""
    mutations = [
        {
            "sequence": 10,
            "table": "line_items",
            "dependencies": [],
            "rows": [{"order_id": "$ref:mutations[5].returning.id", "qty": 2}],
        },
        {
            "sequence": 5,
            "table": "orders",
            "dependencies": [],
            "rows": [{"customer_id": 100}],
        },
    ]
    sorted_muts = topological_sort_mutations(mutations)
    assert [m["sequence"] for m in sorted_muts] == [5, 10]


def test_topological_sort_multi_hop_chain() -> None:
    """Chained mutations A -> B -> C are topologically ordered."""
    mutations = [
        {"sequence": 3, "table": "payments", "dependencies": [2]},
        {"sequence": 1, "table": "users", "dependencies": []},
        {"sequence": 2, "table": "orders", "dependencies": [1]},
    ]
    sorted_muts = topological_sort_mutations(mutations)
    assert [m["sequence"] for m in sorted_muts] == [1, 2, 3]


def test_topological_sort_detects_circular_dependency() -> None:
    """Direct cycle A -> B -> A raises ValueError."""
    mutations = [
        {"sequence": 1, "table": "tbl_a", "dependencies": [2]},
        {"sequence": 2, "table": "tbl_b", "dependencies": [1]},
    ]
    with pytest.raises(ValueError, match="Circular dependency detected"):
        topological_sort_mutations(mutations)


# ==============================================================================
# 2. Dynamic $ref Resolution Tests
# ==============================================================================


def test_resolve_ref_value_scalar() -> None:
    """Dynamic $ref string is resolved to parent's returning value."""
    registry = {0: {"id": 101, "code": "ENG"}}
    val = "$ref:mutations[0].returning.id"
    resolved = resolve_ref_value(val, registry)
    assert resolved == 101


def test_resolve_ref_value_nested_dict() -> None:
    """Nested dictionaries with $ref values are recursively resolved."""
    registry = {1: {"department_id": 42}}
    data = {
        "name": "Alice",
        "dept_ref": "$ref:mutations[1].returning.department_id",
        "nested": {"key": "$ref:mutations[1].returning.department_id"},
    }
    resolved = resolve_ref_value(data, registry)
    assert resolved["dept_ref"] == 42
    assert resolved["nested"]["key"] == 42


def test_resolve_ref_value_unresolved_raises_error() -> None:
    """Missing parent sequence in registry raises clear ValueError."""
    registry = {1: {"id": 10}}
    val = "$ref:mutations[2].returning.id"
    with pytest.raises(ValueError, match="Unable to resolve dynamic reference"):
        resolve_ref_value(val, registry)


def test_resolve_mutation_refs() -> None:
    """Entire mutation dict has all row and filter $ref values resolved."""
    registry = {0: {"id": 999}}
    mutation = {
        "sequence": 1,
        "table": "employees",
        "operation": "insert",
        "rows": [{"dept_id": "$ref:mutations[0].returning.id", "name": "Bob"}],
        "filter": {"org_id": "$ref:mutations[0].returning.id"},
    }
    resolved = resolve_mutation_refs(mutation, registry)
    assert resolved["rows"][0]["dept_id"] == 999
    assert resolved["filter"]["org_id"] == 999


# ==============================================================================
# 3. Transactional Change-Set Execution Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_execute_change_set_insert_success() -> None:
    """Executes single-table INSERT within an atomic transaction and captures returning values."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()

    # Mock context manager engine.begin()
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    # Mock conn.execute returning mapping
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = {"id": 10, "name": "Engineering"}
    mock_conn.execute = AsyncMock(return_value=mock_result)

    change_set = {
        "summary": "Create department",
        "mutations": [
            {
                "sequence": 0,
                "table": "departments",
                "operation": "insert",
                "columns": ["name"],
                "rows": [{"name": "Engineering"}],
            }
        ],
    }

    res = await execute_change_set(
        engine=mock_engine,
        dialect="postgresql",
        change_set=change_set,
    )

    assert res.success is True
    assert res.total_rows_affected == 1
    assert len(res.tables_affected) == 1
    assert res.tables_affected[0]["table"] == "departments"
    assert res.returning_registry[0]["id"] == 10
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_execute_change_set_multi_table_with_dynamic_ref() -> None:
    """Multi-table write resolves parent's returning ID into child's foreign key."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    parent_result = MagicMock()
    parent_result.mappings.return_value.first.return_value = {"id": 77}

    child_result = MagicMock()
    child_result.mappings.return_value.first.return_value = {"id": 888, "department_id": 77}

    mock_conn.execute.side_effect = [parent_result, child_result]

    change_set = {
        "summary": "Create dept and employee",
        "mutations": [
            {
                "sequence": 1,
                "table": "departments",
                "operation": "insert",
                "columns": ["name"],
                "rows": [{"name": "Sales"}],
            },
            {
                "sequence": 2,
                "table": "employees",
                "operation": "insert",
                "columns": ["name", "department_id"],
                "dependencies": [1],
                "rows": [{"name": "John Doe", "department_id": "$ref:mutations[1].returning.id"}],
            },
        ],
    }

    res = await execute_change_set(
        engine=mock_engine,
        dialect="postgresql",
        change_set=change_set,
    )

    assert res.success is True
    assert res.total_rows_affected == 2
    assert res.returning_registry[1]["id"] == 77
    assert res.returning_registry[2]["department_id"] == 77


@pytest.mark.asyncio
async def test_execute_change_set_patch_with_row_locking_and_snapshots() -> None:
    """PATCH executes SELECT FOR UPDATE, verifies preview count, and captures snapshots."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    # 1. Lock result (before snapshot)
    mock_lock_res = MagicMock()
    mock_lock_res.mappings.return_value.all.return_value = [{"id": 1, "status": "pending"}]

    # 2. Update execution result
    mock_update_res = MagicMock()

    # 3. After snapshot result
    mock_after_res = MagicMock()
    mock_after_res.mappings.return_value.all.return_value = [{"id": 1, "status": "active"}]

    mock_conn.execute.side_effect = [mock_lock_res, mock_update_res, mock_after_res]

    change_set = {
        "summary": "Activate user 1",
        "mutations": [
            {
                "sequence": 0,
                "table": "users",
                "operation": "patch",
                "filter": {"id": 1},
                "rows": [{"status": "active"}],
            }
        ],
    }

    res = await execute_change_set(
        engine=mock_engine,
        dialect="postgresql",
        change_set=change_set,
        preview_row_counts={"users": 1},
    )

    assert res.success is True
    assert res.total_rows_affected == 1
    assert "users" in res.before_snapshots
    assert res.before_snapshots["users"][0]["status"] == "pending"
    assert "users" in res.after_snapshots
    assert res.after_snapshots["users"][0]["status"] == "active"
    assert res.before_snapshot_encrypted is not None
    assert res.after_snapshot_encrypted is not None


@pytest.mark.asyncio
async def test_execute_change_set_patch_concurrency_conflict_aborts() -> None:
    """If locked row count does not match preview count, transaction aborts."""
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    # Locked rows returned 0 (e.g. deleted concurrently)
    mock_lock_res = MagicMock()
    mock_lock_res.mappings.return_value.all.return_value = []
    mock_conn.execute.return_value = mock_lock_res

    change_set = {
        "summary": "Update user",
        "mutations": [
            {
                "sequence": 0,
                "table": "users",
                "operation": "patch",
                "filter": {"id": 1},
                "rows": [{"status": "active"}],
            }
        ],
    }

    res = await execute_change_set(
        engine=mock_engine,
        dialect="postgresql",
        change_set=change_set,
        preview_row_counts={"users": 1},
    )

    assert res.success is False
    assert "Concurrency conflict" in str(res.error_message)


# ==============================================================================
# 4. ChatService.execute_mutation Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_chat_service_execute_mutation_success() -> None:
    """ChatService.execute_mutation executes transaction, updates status, and logs audit."""
    owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id

    mock_session = MagicMock(spec=ChatSession)
    mock_session.id = session_id

    mock_conn_model = MagicMock(spec=Connection)
    mock_conn_model.id = connection_id
    mock_conn_model.dialect = "postgresql"
    mock_conn_model.encrypted_connection_string = "encrypted_str"

    change_set = {
        "summary": "Add new product",
        "mutations": [
            {
                "sequence": 0,
                "table": "products",
                "operation": "insert",
                "columns": ["title", "price"],
                "rows": [{"title": "Widget", "price": 9.99}],
            }
        ],
    }
    cs_hash = compute_change_set_hash(change_set)
    cs_encrypted = encrypt_secret(json.dumps(change_set))

    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.project_id = project_id
    mock_mutation.session_id = session_id
    mock_mutation.connection_id = connection_id
    mock_mutation.proposer_id = owner_id
    mock_mutation.status = "APPROVED"
    mock_mutation.change_set_encrypted = cs_encrypted
    mock_mutation.change_set_hash = cs_hash
    mock_mutation.preview_row_counts = {"products": 1}

    mock_db = MagicMock()
    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    mock_conn_svc = MagicMock()
    mock_conn_svc.get_connection = AsyncMock(return_value=mock_conn_model)

    mock_ws = MagicMock()
    mock_ws.send_event = AsyncMock()

    service = ChatService(
        db=mock_db,
        project_service=mock_proj_svc,
        connection_service=mock_conn_svc,
        ws_manager=mock_ws,
    )
    service.get_mutation = AsyncMock(return_value=mock_mutation)
    service._mutation_repo.update_status = AsyncMock(return_value=mock_mutation)
    service._audit_repo.create_log = AsyncMock()
    service._message_repo.create_message = AsyncMock()

    mock_exec_res = ExecutionResult(
        success=True,
        total_rows_affected=1,
        tables_affected=[{"table": "products", "operation": "insert", "row_count": 1}],
        latency_ms=15,
        before_snapshot_encrypted=None,
        after_snapshot_encrypted=None,
    )

    with patch(
        "app.domain.chat.services.execute_change_set",
        new=AsyncMock(return_value=mock_exec_res),
    ), patch(
        "app.domain.chat.services.connection_manager.get_engine",
        return_value=MagicMock(),
    ):
        result = await service.execute_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
        )

        assert result == mock_mutation
        # Verify status transitions (EXECUTING -> EXECUTED)
        assert service._mutation_repo.update_status.call_count == 2
        last_status_call = service._mutation_repo.update_status.call_args_list[-1]
        assert last_status_call[1]["status"] == "EXECUTED"
        assert last_status_call[1]["total_rows_affected"] == 1

        # Verify audit log was recorded
        service._audit_repo.create_log.assert_called_once()
        audit_kwargs = service._audit_repo.create_log.call_args[1]
        assert audit_kwargs["status"] == "executed"
        assert audit_kwargs["total_rows_affected"] == 1
        assert audit_kwargs["change_set_hash"] == cs_hash

        # Verify WebSocket events sent
        ws_events = [call[1]["event_type"] for call in mock_ws.send_event.call_args_list]
        assert "mutation_executing" in ws_events
        assert "mutation_executed" in ws_events


@pytest.mark.asyncio
async def test_chat_service_execute_mutation_tamper_detection() -> None:
    """Tampered change-set payload triggers tamper detection and raises BadRequestException."""
    owner_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.owner_id = owner_id

    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.status = "APPROVED"
    mock_mutation.change_set_encrypted = encrypt_secret(json.dumps({"summary": "altered"}))
    mock_mutation.change_set_hash = "different_unmatched_hash"

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    service = ChatService(
        db=MagicMock(),
        project_service=mock_proj_svc,
        connection_service=MagicMock(),
    )
    service.get_mutation = AsyncMock(return_value=mock_mutation)

    with pytest.raises(BadRequestException, match="tamper detection"):
        await service.execute_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
        )


@pytest.mark.asyncio
async def test_chat_service_execute_mutation_forbidden_for_non_owner() -> None:
    """Non-owner user cannot execute mutations."""
    owner_id = uuid.uuid4()
    non_owner_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.owner_id = owner_id

    mock_proj_svc = MagicMock()
    mock_proj_svc.get_project = AsyncMock(return_value=mock_project)

    service = ChatService(
        db=MagicMock(),
        project_service=mock_proj_svc,
        connection_service=MagicMock(),
    )

    with pytest.raises(ForbiddenException, match="Only the project owner"):
        await service.execute_mutation(
            project_id=project_id,
            session_id=uuid.uuid4(),
            mutation_id=uuid.uuid4(),
            user_id=non_owner_id,
        )
