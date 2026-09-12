"""
Unit and integration tests for Phase 2:
- Connection write policy defaults, updates, and validations.
- Extended schema metadata reflection & persistence (defaults, generated, identity, constraints).
- PendingMutation repository CRUD and status transitions.
- MutationAuditLog repository append-only persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, encrypt_secret, get_password_hash
from app.domain.auth.models import User
from app.domain.chat.repository import (
    MutationAuditLogRepository,
    PendingMutationRepository,
)
from app.domain.connections.models import Connection
from app.domain.connections.schemas import ConnectionUpdate
from app.domain.connections.services import ConnectionService
from app.domain.projects.models import Project
from app.domain.projects.services import ProjectService
from app.domain.schema_introspection.repository import SchemaIntrospectionRepository


async def _create_test_environment(
    db: AsyncSession,
) -> tuple[User, Project, Connection, dict[str, str]]:
    """Helper to create user, project, and connection."""
    user = User(
        email=f"phase2_{uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("ValidPass123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    project = Project(
        name="Phase 2 Project",
        description="Testing Phase 2 models and policies",
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    conn = Connection(
        project_id=project.id,
        name="Phase 2 DB",
        dialect="postgresql",
        encrypted_connection_string=encrypt_secret("postgresql://test:test@localhost:5432/testdb"),
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    return user, project, conn, headers


@pytest.mark.asyncio
async def test_connection_write_policy_defaults_and_updates(db_session: AsyncSession) -> None:
    """Test that connections have expected default write policies and can be updated."""
    user, project, conn, _ = await _create_test_environment(db_session)

    # 1. Verify default write policy values
    assert conn.writes_enabled is False
    assert conn.max_insert_rows_per_table == 5
    assert conn.max_patch_rows_per_table == 1
    assert conn.max_total_rows_per_changeset == 10
    assert conn.max_tables_per_changeset == 1
    assert conn.approval_timeout_minutes == 15
    assert conn.undo_window_minutes == 0
    assert conn.blocked_tables is None

    # 2. Update write policy via service
    proj_svc = ProjectService(db_session)
    conn_svc = ConnectionService(db_session, proj_svc)

    update_data = ConnectionUpdate(
        writes_enabled=True,
        max_insert_rows_per_table=20,
        max_patch_rows_per_table=5,
        max_total_rows_per_changeset=50,
        max_tables_per_changeset=3,
        approval_timeout_minutes=30,
        undo_window_minutes=60,
        blocked_tables=["users", "salaries"],
    )

    updated_conn = await conn_svc.update_connection(
        project_id=project.id,
        data=update_data,
        user_id=user.id,
    )

    assert updated_conn.writes_enabled is True
    assert updated_conn.max_insert_rows_per_table == 20
    assert updated_conn.max_patch_rows_per_table == 5
    assert updated_conn.max_total_rows_per_changeset == 50
    assert updated_conn.max_tables_per_changeset == 3
    assert updated_conn.approval_timeout_minutes == 30
    assert updated_conn.undo_window_minutes == 60
    assert updated_conn.blocked_tables == ["users", "salaries"]


@pytest.mark.asyncio
async def test_connection_patch_api_returns_write_policy(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test updating write policy via HTTP PATCH endpoint."""
    user, project, conn, headers = await _create_test_environment(db_session)

    res = await client.patch(
        f"/api/v1/projects/{project.id}/connections",
        json={"writes_enabled": True, "max_patch_rows_per_table": 10},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["writes_enabled"] is True
    assert data["max_patch_rows_per_table"] == 10
    assert data["max_insert_rows_per_table"] == 5


@pytest.mark.asyncio
async def test_schema_metadata_persistence(db_session: AsyncSession) -> None:
    """Test persisting extended column metadata (defaults, identity, autoincrement, constraints)."""
    user, project, conn, _ = await _create_test_environment(db_session)
    repo = SchemaIntrospectionRepository(db_session)

    tables_data = [
        {
            "schema_name": "public",
            "table_name": "users",
            "unique_constraints": [{"name": "uq_users_email", "column_names": ["email"]}],
            "check_constraints": [{"name": "chk_positive_age", "sqltext": "age > 0"}],
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False,
                    "ordinal_position": 1,
                    "column_default": "nextval('users_id_seq')",
                    "is_read_only": True,
                },
                {
                    "name": "email",
                    "type": "VARCHAR(255)",
                    "nullable": False,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "ordinal_position": 2,
                    "column_default": None,
                    "is_read_only": False,
                },
                {
                    "name": "full_name",
                    "type": "VARCHAR(255)",
                    "nullable": True,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "ordinal_position": 3,
                    "column_default": "'Anonymous'",
                    "is_read_only": True,
                },
            ],
        }
    ]

    cache = await repo.save_introspected_schema(
        project_id=project.id,
        connection_id=conn.id,
        raw_schema={"tables": {}},
        tables_data=tables_data,
    )

    assert len(cache.tables) == 1
    table = cache.tables[0]
    assert table.table_name == "users"
    assert table.unique_constraints == [{"name": "uq_users_email", "column_names": ["email"]}]
    assert table.check_constraints == [{"name": "chk_positive_age", "sqltext": "age > 0"}]

    cols_by_name = {c.column_name: c for c in table.columns}
    assert cols_by_name["id"].is_read_only is True
    assert cols_by_name["id"].column_default == "nextval('users_id_seq')"
    assert cols_by_name["full_name"].is_read_only is True
    assert cols_by_name["full_name"].column_default == "'Anonymous'"
    assert cols_by_name["email"].is_read_only is False


@pytest.mark.asyncio
async def test_pending_mutation_repository_lifecycle(db_session: AsyncSession) -> None:
    """Test PendingMutation creation, retrieval by hash/idempotency, and status updates."""
    user, project, conn, _ = await _create_test_environment(db_session)
    session_id = uuid4()

    repo = PendingMutationRepository(db_session)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=15)

    # 1. Create mutation
    mutation = await repo.create_mutation(
        project_id=project.id,
        session_id=session_id,
        connection_id=conn.id,
        proposer_id=user.id,
        change_set_encrypted="gAAAAAB...",
        change_set_hash="sha256_mock_hash_123456",
        expires_at=expires_at,
        preview_row_counts={"orders": 1},
        idempotency_key="idemp_key_abc",
        status="PENDING_APPROVAL",
    )
    assert mutation.id is not None
    assert mutation.status == "PENDING_APPROVAL"
    assert mutation.idempotency_key == "idemp_key_abc"

    # 2. Get by idempotency key
    found = await repo.get_by_idempotency_key("idemp_key_abc", project.id)
    assert found is not None
    assert found.id == mutation.id

    # 3. Update status to APPROVED then EXECUTED
    approver_id = uuid4()
    updated = await repo.update_status(
        mutation=mutation,
        status="APPROVED",
        approver_id=approver_id,
    )
    assert updated.status == "APPROVED"
    assert updated.approver_id == approver_id
    assert updated.approved_at is not None

    executed = await repo.update_status(
        mutation=mutation,
        status="EXECUTED",
        total_rows_affected=1,
        execution_result_encrypted="gAAAAAB_result...",
    )
    assert executed.status == "EXECUTED"
    assert executed.total_rows_affected == 1
    assert executed.executed_at is not None


@pytest.mark.asyncio
async def test_mutation_audit_log_repository(db_session: AsyncSession) -> None:
    """Test appending immutable records to MutationAuditLogRepository."""
    user, project, conn, _ = await _create_test_environment(db_session)
    repo = MutationAuditLogRepository(db_session)

    log_entry = await repo.create_log(
        project_id=project.id,
        connection_id=conn.id,
        initiator_id=user.id,
        approver_id=user.id,
        operation="patch",
        change_set_hash="sha256_audit_hash_abc",
        status="executed",
        tables_affected=[{"table": "orders", "operation": "patch", "row_count": 2}],
        total_rows_affected=2,
        before_snapshot_encrypted="gAAAAAB_before...",
        after_snapshot_encrypted="gAAAAAB_after...",
        latency_ms=145,
    )
    assert log_entry.id is not None
    assert log_entry.operation == "patch"
    assert log_entry.total_rows_affected == 2
    assert log_entry.status == "executed"

    # List logs by project
    logs, total = await repo.list_by_project(project.id)
    assert total >= 1
    assert any(log.id == log_entry.id for log in logs)
