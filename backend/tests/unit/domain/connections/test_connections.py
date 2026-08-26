"""
Unit and API integration tests for the Connections domain.

Tests:
- Connection creation with auto-test and encryption.
- Verification that plaintext connection string is NEVER returned.
- Connection update and deletion (including engine disposal).
- Direct and saved connectivity testing endpoints.
- Read-only execution guardrails (blocking DDL/DML).
- Multi-tenant cross-user project isolation.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decrypt, get_password_hash
from app.domain.auth.models import User
from app.domain.connections.manager import connection_manager
from app.domain.connections.models import Connection
from app.domain.projects.schemas import ProjectCreate
from app.domain.projects.services import ProjectService

TEST_SQLITE_TARGET = "sqlite+aiosqlite:///:memory:"


async def create_test_user_and_project(
    db: AsyncSession, email: str = "conn_user@example.com"
) -> tuple[User, dict[str, str], uuid.UUID]:
    """Helper to create user, auth headers, and a project."""
    user = User(
        email=email,
        hashed_password=get_password_hash("ValidPassword123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    project_service = ProjectService(db)
    project = await project_service.create_project(
        data=ProjectCreate(name="Conn Test Project"),
        owner_id=user.id,
    )
    return user, headers, project.id


@pytest.mark.asyncio
async def test_create_connection_success(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers, project_id = await create_test_user_and_project(
        db_session, email="create_conn@example.com"
    )

    payload = {
        "name": "Primary Database",
        "dialect": "sqlite",
        "connection_string": TEST_SQLITE_TARGET,
    }
    response = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Connection established and saved successfully"
    assert body["data"]["name"] == "Primary Database"
    assert body["data"]["dialect"] == "sqlite"
    assert body["data"]["project_id"] == str(project_id)
    # Ensure plaintext string is NOT in response
    assert "connection_string" not in body["data"]
    assert "encrypted_connection_string" not in body["data"]

    # Verify encrypted storage in platform DB
    conn = await db_session.get(Connection, uuid.UUID(body["data"]["id"]))
    assert conn is not None
    assert conn.encrypted_connection_string != TEST_SQLITE_TARGET
    assert decrypt(conn.encrypted_connection_string) == TEST_SQLITE_TARGET


@pytest.mark.asyncio
async def test_create_connection_fails_on_unreachable_target(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="bad_conn@example.com"
    )

    bad_payload = {
        "name": "Unreachable DB",
        "dialect": "postgresql",
        "connection_string": "postgresql+asyncpg://invalid_user:secret_pass@127.0.0.1:54329/nonexistent",
    }
    response = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json=bad_payload,
        headers=headers,
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONNECTION_TEST_FAILED"
    # Ensure password is masked if reflected in error message
    assert "secret_pass" not in str(body["error"])


@pytest.mark.asyncio
async def test_create_duplicate_connection_fails(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="dup_conn@example.com"
    )

    payload = {
        "name": "DB 1",
        "dialect": "sqlite",
        "connection_string": TEST_SQLITE_TARGET,
    }
    # First creation succeeds
    res1 = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json=payload,
        headers=headers,
    )
    assert res1.status_code == 201

    # Second creation fails with 409 Conflict
    res2 = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json=payload,
        headers=headers,
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "CONNECTION_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_get_connection_by_project(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="get_conn@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "My SQLite",
            "dialect": "sqlite",
            "connection_string": TEST_SQLITE_TARGET,
        },
        headers=headers,
    )

    res = await client.get(f"/api/v1/projects/{project_id}/connections", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["name"] == "My SQLite"


@pytest.mark.asyncio
async def test_get_connection_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="noconn@example.com"
    )

    res = await client.get(f"/api/v1/projects/{project_id}/connections", headers=headers)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CONNECTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_and_delete_connection(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="update_conn@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "Initial Name",
            "dialect": "sqlite",
            "connection_string": TEST_SQLITE_TARGET,
        },
        headers=headers,
    )

    # Patch name
    patch_res = await client.patch(
        f"/api/v1/projects/{project_id}/connections",
        json={"name": "Renamed Connection"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["name"] == "Renamed Connection"

    # Delete connection
    del_res = await client.delete(f"/api/v1/projects/{project_id}/connections", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Check deleted
    get_res = await client.get(f"/api/v1/projects/{project_id}/connections", headers=headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_test_connection_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project_id = await create_test_user_and_project(
        db_session, email="test_endpoint@example.com"
    )

    # 1. Test directly with raw connection string payload
    test_res1 = await client.post(
        f"/api/v1/projects/{project_id}/connections/test",
        json={"connection_string": TEST_SQLITE_TARGET, "dialect": "sqlite"},
        headers=headers,
    )
    assert test_res1.status_code == 200
    body1 = test_res1.json()
    assert body1["data"]["success"] is True
    assert body1["data"]["latency_ms"] is not None

    # 2. Save connection and test stored credentials
    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "Stored SQLite",
            "dialect": "sqlite",
            "connection_string": TEST_SQLITE_TARGET,
        },
        headers=headers,
    )

    test_res2 = await client.post(
        f"/api/v1/projects/{project_id}/connections/test",
        headers=headers,
    )
    assert test_res2.status_code == 200
    body2 = test_res2.json()
    assert body2["data"]["success"] is True


@pytest.mark.asyncio
async def test_connection_cross_user_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers1, project1_id = await create_test_user_and_project(
        db_session, email="user_one@example.com"
    )
    _, headers2, _ = await create_test_user_and_project(
        db_session, email="user_two@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project1_id}/connections",
        json={
            "name": "User 1 DB",
            "dialect": "sqlite",
            "connection_string": TEST_SQLITE_TARGET,
        },
        headers=headers1,
    )

    # User 2 tries to access User 1's connection -> 404
    res = await client.get(f"/api/v1/projects/{project1_id}/connections", headers=headers2)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_connection_manager_guardrails() -> None:
    # Test blocked keywords
    with pytest.raises(ValueError, match="Blocked keyword 'drop' detected"):
        connection_manager._validate_query("DROP TABLE users;")

    with pytest.raises(ValueError, match="Blocked keyword 'delete' detected"):
        connection_manager._validate_query("DELETE FROM orders WHERE id = 1;")

    with pytest.raises(ValueError, match="Blocked keyword 'insert' detected"):
        connection_manager._validate_query("INSERT INTO customers VALUES (1, 'Acme');")


def test_normalize_connection_url() -> None:
    from app.domain.connections.manager import normalize_connection_url

    # PostgreSQL standard URLs
    assert (
        normalize_connection_url("postgresql://user:pass@localhost:5432/mydb")
        == "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    )
    assert (
        normalize_connection_url("postgres://user:pass@localhost:5432/mydb")
        == "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    )
    # Already explicit driver
    assert (
        normalize_connection_url("postgresql+asyncpg://user:pass@localhost:5432/mydb")
        == "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    )
    # SQLite
    assert (
        normalize_connection_url("sqlite:///data.db")
        == "sqlite+aiosqlite:///data.db"
    )
    assert (
        normalize_connection_url("sqlite+aiosqlite:///:memory:")
        == "sqlite+aiosqlite:///:memory:"
    )
    # MySQL / MariaDB
    assert (
        normalize_connection_url("mysql://user:pass@localhost:3306/mydb")
        == "mysql+asyncmy://user:pass@localhost:3306/mydb"
    )
    assert (
        normalize_connection_url("mariadb://user:pass@localhost:3306/mydb")
        == "mariadb+asyncmy://user:pass@localhost:3306/mydb"
    )


def test_fernet_key_derivation() -> None:
    from cryptography.fernet import Fernet
    from app.core.security import _derive_fernet_key

    # Arbitrary strings (like placeholders in .env) should derive a valid Fernet key
    derived = _derive_fernet_key("generate_with_python_cryptography")
    fernet = Fernet(derived)
    token = fernet.encrypt(b"secret")
    assert fernet.decrypt(token) == b"secret"

    # Valid base64 32-byte key should be preserved
    valid_key = "q1M8rN0sK2vP4_tX6wZ8yB0cE2gH4jL6nQ8sU0wY2zA="
    assert _derive_fernet_key(valid_key) == valid_key.encode("utf-8")
