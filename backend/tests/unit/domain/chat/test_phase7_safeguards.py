"""Unit tests for Phase 7: Advanced Safeguards (Dry-Run, Rate Limiting, Concurrency Conflicts, Soft-Undo)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.mutation_executor import (
    execute_change_set,
    execute_undo_change_set,
)
from app.domain.agent.nodes.mutation_previewer import create_mutation_previewer_node
from app.domain.agent.state import AgentState
from app.domain.chat.models import PendingMutation
from app.domain.chat.rate_limiter import (
    MutationRateLimiter,
)
from app.domain.chat.services import ChatService
from app.domain.connections.models import Connection
from app.domain.projects.models import Project

# ---------------------------------------------------------------------------
# 1. Rate Limiter Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limiter_session_pending_cap() -> None:
    """Verify session pending mutation limit (max 3)."""
    limiter = MutationRateLimiter()
    mock_db = AsyncMock()

    project_id = uuid.uuid4()
    session_id = uuid.uuid4()

    # Case 1: 2 pending mutations (within limit)
    mock_result_ok = MagicMock()
    mock_result_ok.scalar_one.return_value = 2
    mock_db.execute.return_value = mock_result_ok

    await limiter.check_session_pending_limit(mock_db, project_id, session_id)

    # Case 2: 3 pending mutations (cap reached)
    mock_result_capped = MagicMock()
    mock_result_capped.scalar_one.return_value = 3
    mock_db.execute.return_value = mock_result_capped

    with pytest.raises(BadRequestException) as exc:
        await limiter.check_session_pending_limit(mock_db, project_id, session_id)
    assert exc.value.error_code == "MAX_PENDING_MUTATIONS_REACHED"


@pytest.mark.asyncio
async def test_rate_limiter_project_hourly_limits() -> None:
    """Verify project hourly write and row caps (30 writes, 200 rows)."""
    limiter = MutationRateLimiter()
    mock_db = AsyncMock()
    project_id = uuid.uuid4()

    # Case 1: Within limits (10 writes, 50 rows)
    mock_res_1 = MagicMock()
    mock_res_1.one.return_value = (10, 50)
    mock_db.execute.return_value = mock_res_1
    await limiter.check_project_hourly_limits(mock_db, project_id)

    # Case 2: Write limit exceeded (30 writes)
    mock_res_2 = MagicMock()
    mock_res_2.one.return_value = (30, 50)
    mock_db.execute.return_value = mock_res_2
    with pytest.raises(BadRequestException) as exc_writes:
        await limiter.check_project_hourly_limits(mock_db, project_id)
    assert exc_writes.value.error_code == "HOURLY_WRITE_LIMIT_EXCEEDED"

    # Case 3: Row limit exceeded (200 rows)
    mock_res_3 = MagicMock()
    mock_res_3.one.return_value = (5, 200)
    mock_db.execute.return_value = mock_res_3
    with pytest.raises(BadRequestException) as exc_rows:
        await limiter.check_project_hourly_limits(mock_db, project_id)
    assert exc_rows.value.error_code == "HOURLY_ROW_CAP_EXCEEDED"


def test_rate_limiter_failure_cooldown() -> None:
    """Verify 60-second cooldown after a failed execution."""
    limiter = MutationRateLimiter()
    session_id = uuid.uuid4()

    # No failure recorded -> passes
    limiter.check_failure_cooldown(session_id)

    # Record failure
    limiter.record_failure(session_id)

    # Within 60s -> raises BadRequestException
    with pytest.raises(BadRequestException) as exc:
        limiter.check_failure_cooldown(session_id)
    assert exc.value.error_code == "WRITE_COOLDOWN_ACTIVE"

    # Clear cooldown -> passes
    limiter.clear_failure_cooldown(session_id)
    limiter.check_failure_cooldown(session_id)


# ---------------------------------------------------------------------------
# 2. Dry-Run Mode Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_mode_bypasses_staging() -> None:
    """Verify dry_run: true generates preview and emits frame without creating PendingMutation in DB."""
    mock_ws = AsyncMock()
    mock_conn = MagicMock(spec=Connection)
    mock_conn.id = uuid.uuid4()
    mock_conn.project_id = uuid.uuid4()
    mock_conn.max_patch_rows_per_table = 20
    mock_conn.approval_timeout_minutes = 15

    deps = MagicMock(spec=GraphDependencies)
    deps.connection = mock_conn
    deps.ws_manager = mock_ws
    deps.db = AsyncMock()
    deps.connection_manager = None

    previewer_node = create_mutation_previewer_node(deps)

    change_set: dict[str, Any] = {
        "summary": "Dry-run insert",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "departments",
                "rows": [{"name": "QA", "code": "QA"}],
            }
        ],
    }

    state: AgentState = {
        "project_id": mock_conn.project_id,
        "session_id": uuid.uuid4(),
        "connection_id": mock_conn.id,
        "user_id": uuid.uuid4(),
        "mutation_change_set": change_set,
        "dry_run": True,
    }

    result = await previewer_node(state)

    # Result indicates DRY_RUN_COMPLETED
    assert result["mutation_status"] == "DRY_RUN_COMPLETED"
    assert "Dry-Run" in result["nl_summary"]

    # PendingMutationRepository was NOT called to persist mutation
    deps.db.add.assert_not_called()

    # WebSocket received mutation_preview with dry_run: True
    mock_ws.send_event.assert_called_once()
    call_args = mock_ws.send_event.call_args[1]
    assert call_args["event_type"] == "mutation_preview"
    assert call_args["data"]["dry_run"] is True


# ---------------------------------------------------------------------------
# 3. Concurrency Conflict Detection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_conflict_on_patch_timestamp_drift() -> None:
    """Verify that updating a row whose updated_at changed since preview aborts the transaction."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE items ("
                "id INTEGER PRIMARY KEY, "
                "name TEXT, "
                "updated_at TEXT"
                ")"
            )
        )
        await conn.execute(
            text("INSERT INTO items (id, name, updated_at) VALUES (1, 'Widget', '2026-01-01T10:00:00Z')")
        )

    # Candidate rows recorded during preview had timestamp '2026-01-01T09:00:00Z' (outdated!)
    outdated_candidate_rows = [
        {"id": 1, "name": "Widget", "updated_at": "2026-01-01T09:00:00Z"}
    ]

    change_set = {
        "summary": "Update item name",
        "mutations": [
            {
                "sequence": 1,
                "operation": "patch",
                "table": "items",
                "filter": {"id": 1},
                "rows": [{"name": "Updated Widget"}],
            }
        ],
        "candidate_rows": {"items": outdated_candidate_rows},
    }

    exec_res = await execute_change_set(
        engine=engine,
        dialect="sqlite",
        change_set=change_set,
        preview_row_counts={"items": 1},
    )

    # Must fail with Concurrency conflict
    assert exec_res.success is False
    assert "Concurrency conflict" in (exec_res.error_message or "")
    assert "was modified concurrently" in (exec_res.error_message or "")

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrency_conflict_on_insert_existing_id() -> None:
    """Verify that inserting an explicitly provided ID that already exists aborts the transaction."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        await conn.execute(text("INSERT INTO items (id, name) VALUES (42, 'Existing Item')"))

    change_set = {
        "summary": "Insert duplicate item id",
        "mutations": [
            {
                "sequence": 1,
                "operation": "insert",
                "table": "items",
                "rows": [{"id": 42, "name": "Duplicate Item"}],
            }
        ],
    }

    exec_res = await execute_change_set(
        engine=engine,
        dialect="sqlite",
        change_set=change_set,
    )

    assert exec_res.success is False
    assert "conflicting row with id=42 already exists" in (exec_res.error_message or "")

    await engine.dispose()


# ---------------------------------------------------------------------------
# 4. Soft-Undo Engine Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_undo_change_set_reverts_insert_and_patch() -> None:
    """Verify execute_undo_change_set deletes inserted rows and restores before_snapshots for patched rows."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL)"))
        await conn.execute(text("INSERT INTO items (id, name, price) VALUES (1, 'Old Widget', 10.0)"))
        await conn.execute(text("INSERT INTO items (id, name, price) VALUES (2, 'New Widget', 25.0)"))

    # Assume mutation 1 updated item 1 to name='New Widget', price=30.0
    # Mutation 2 inserted item 2
    change_set = {
        "summary": "Patch item 1 and insert item 2",
        "mutations": [
            {
                "sequence": 1,
                "operation": "patch",
                "table": "items",
                "filter": {"id": 1},
                "rows": [{"name": "New Widget", "price": 30.0}],
            },
            {
                "sequence": 2,
                "operation": "insert",
                "table": "items",
                "rows": [{"id": 2, "name": "New Widget", "price": 25.0}],
            },
        ],
    }

    # Before snapshot captured original item 1
    before_snapshots = {
        "items": [{"id": 1, "name": "Old Widget", "price": 10.0}]
    }

    undo_res = await execute_undo_change_set(
        engine=engine,
        dialect="sqlite",
        change_set=change_set,
        before_snapshots=before_snapshots,
    )

    assert undo_res.success is True
    assert undo_res.total_rows_affected == 2  # 1 deleted, 1 restored

    # Check database state
    async with engine.connect() as conn:
        # Item 1 should have original values
        r1 = (await conn.execute(text("SELECT name, price FROM items WHERE id = 1"))).one()
        assert r1[0] == "Old Widget"
        assert r1[1] == 10.0

        # Item 2 should be deleted
        r2 = (await conn.execute(text("SELECT count(*) FROM items WHERE id = 2"))).scalar()
        assert r2 == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_undo_mutation_service_permission_and_window_checks() -> None:
    """Verify ChatService.undo_mutation enforces owner permission, undo_window > 0, and expiration."""
    mock_db = AsyncMock()
    mock_ws = AsyncMock()
    mock_project_service = AsyncMock()
    mock_connection_service = AsyncMock()
    chat_service = ChatService(
        db=mock_db,
        project_service=mock_project_service,
        connection_service=mock_connection_service,
        ws_manager=mock_ws,
    )

    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mutation_id = uuid.uuid4()

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = owner_id

    chat_service._project_service = AsyncMock()
    chat_service._project_service.get_project.return_value = mock_project

    # 1. Non-owner rejection
    with pytest.raises(ForbiddenException) as exc_perm:
        await chat_service.undo_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=other_user_id,
        )
    assert exc_perm.value.error_code == "MUTATION_UNDO_FORBIDDEN"

    # 2. Status not EXECUTED
    mock_mutation = MagicMock(spec=PendingMutation)
    mock_mutation.id = mutation_id
    mock_mutation.status = "PENDING_APPROVAL"
    chat_service.get_mutation = AsyncMock(return_value=mock_mutation)

    with pytest.raises(BadRequestException) as exc_status:
        await chat_service.undo_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
        )
    assert exc_status.value.error_code == "INVALID_MUTATION_STATUS"

    # 3. Undo disabled (undo_window_minutes == 0)
    mock_mutation.status = "EXECUTED"
    mock_conn = MagicMock(spec=Connection)
    mock_conn.undo_window_minutes = 0
    chat_service._connection_service = AsyncMock()
    chat_service._connection_service.get_connection.return_value = mock_conn

    with pytest.raises(BadRequestException) as exc_disabled:
        await chat_service.undo_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
        )
    assert exc_disabled.value.error_code == "UNDO_DISABLED"

    # 4. Undo window expired
    mock_conn.undo_window_minutes = 10
    mock_mutation.executed_at = datetime.now(tz=UTC) - timedelta(minutes=15)

    with pytest.raises(BadRequestException) as exc_expired:
        await chat_service.undo_mutation(
            project_id=project_id,
            session_id=session_id,
            mutation_id=mutation_id,
            user_id=owner_id,
        )
    assert exc_expired.value.error_code == "UNDO_WINDOW_EXPIRED"
