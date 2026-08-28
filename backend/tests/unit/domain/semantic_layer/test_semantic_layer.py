"""
Unit and API integration tests for the SemanticLayer domain.

Tests:
- Table annotation creation and retrieval.
- Column annotation creation and retrieval.
- Payload validation for mutually exclusive IDs.
- Annotation listing with target_type filters.
- Updating and deleting annotations.
- Multi-tenant ownership checks.
- Standardized ApiResponse envelope validation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.domain.auth.models import User
from app.domain.connections.models import Connection
from app.domain.projects.models import Project
from app.domain.schema_introspection.models import SchemaCache, SchemaColumn, SchemaTable


async def setup_test_context(
    db: AsyncSession, email: str = "annotator@example.com"
) -> tuple[User, dict[str, str], Project, Connection, SchemaTable, SchemaColumn]:
    """Helper to set up user, project, connection, table, and column entities."""
    user = User(
        email=email,
        hashed_password=get_password_hash("Password123!"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    project = Project(
        name="Test Analytics Project",
        description="Testing semantic annotations",
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    connection = Connection(
        project_id=project.id,
        name="Main Postgres DB",
        dialect="postgresql",
        encrypted_connection_string="gAAAAABtest_encrypted_string",
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    cache = SchemaCache(
        project_id=project.id,
        connection_id=connection.id,
        raw_schema={"tables": {}},
    )
    db.add(cache)
    await db.commit()
    await db.refresh(cache)

    table = SchemaTable(
        cache_id=cache.id,
        project_id=project.id,
        connection_id=connection.id,
        schema_name="public",
        table_name="customers",
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)

    column = SchemaColumn(
        table_id=table.id,
        project_id=project.id,
        connection_id=connection.id,
        column_name="email",
        data_type="VARCHAR(255)",
        ordinal_position=1,
    )
    db.add(column)
    await db.commit()
    await db.refresh(column)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    return user, headers, project, connection, table, column


@pytest.mark.asyncio
async def test_create_table_annotation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project, _, table, _ = await setup_test_context(db_session, "user1@test.com")

    payload = {
        "target_type": "table",
        "schema_table_id": str(table.id),
        "note": "Stores all active customer profiles and contact details.",
    }

    response = await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["target_type"] == "table"
    assert body["data"]["schema_table_id"] == str(table.id)
    assert body["data"]["schema_column_id"] is None
    assert body["data"]["note"] == "Stores all active customer profiles and contact details."


@pytest.mark.asyncio
async def test_create_column_annotation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project, _, _, column = await setup_test_context(db_session, "user2@test.com")

    payload = {
        "target_type": "column",
        "schema_column_id": str(column.id),
        "note": "Primary email address used for customer authentication and notifications.",
    }

    response = await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["target_type"] == "column"
    assert body["data"]["schema_column_id"] == str(column.id)
    assert body["data"]["schema_table_id"] is None
    assert body["data"]["note"] == "Primary email address used for customer authentication and notifications."


@pytest.mark.asyncio
async def test_create_annotation_invalid_payload(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project, _, table, column = await setup_test_context(db_session, "user3@test.com")

    # Mismatched target_type 'table' with column_id provided
    bad_payload_1 = {
        "target_type": "table",
        "schema_column_id": str(column.id),
        "note": "Invalid note",
    }
    res1 = await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json=bad_payload_1,
        headers=headers,
    )
    assert res1.status_code == 422

    # Both IDs provided
    bad_payload_2 = {
        "target_type": "table",
        "schema_table_id": str(table.id),
        "schema_column_id": str(column.id),
        "note": "Invalid note",
    }
    res2 = await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json=bad_payload_2,
        headers=headers,
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_list_and_filter_annotations(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project, _, table, column = await setup_test_context(db_session, "user4@test.com")

    # Create 1 table annotation and 1 column annotation
    await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json={"target_type": "table", "schema_table_id": str(table.id), "note": "Table note"},
        headers=headers,
    )
    await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json={"target_type": "column", "schema_column_id": str(column.id), "note": "Column note"},
        headers=headers,
    )

    # List all
    res_all = await client.get(f"/api/v1/projects/{project.id}/annotations", headers=headers)
    assert res_all.status_code == 200
    assert len(res_all.json()["data"]) == 2

    # Filter table
    res_tables = await client.get(
        f"/api/v1/projects/{project.id}/annotations?target_type=table",
        headers=headers,
    )
    assert res_tables.status_code == 200
    assert len(res_tables.json()["data"]) == 1
    assert res_tables.json()["data"][0]["target_type"] == "table"

    # Filter column
    res_cols = await client.get(
        f"/api/v1/projects/{project.id}/annotations?target_type=column",
        headers=headers,
    )
    assert res_cols.status_code == 200
    assert len(res_cols.json()["data"]) == 1
    assert res_cols.json()["data"][0]["target_type"] == "column"


@pytest.mark.asyncio
async def test_update_and_delete_annotation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers, project, _, table, _ = await setup_test_context(db_session, "user5@test.com")

    # Create
    create_res = await client.post(
        f"/api/v1/projects/{project.id}/annotations",
        json={"target_type": "table", "schema_table_id": str(table.id), "note": "Initial note"},
        headers=headers,
    )
    annotation_id = create_res.json()["data"]["id"]

    # Get single
    get_res = await client.get(
        f"/api/v1/projects/{project.id}/annotations/{annotation_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["data"]["note"] == "Initial note"

    # Update
    update_res = await client.put(
        f"/api/v1/projects/{project.id}/annotations/{annotation_id}",
        json={"note": "Updated table description"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["note"] == "Updated table description"

    # Delete
    del_res = await client.delete(
        f"/api/v1/projects/{project.id}/annotations/{annotation_id}",
        headers=headers,
    )
    assert del_res.status_code == 200

    # Verify deleted
    get_after_del = await client.get(
        f"/api/v1/projects/{project.id}/annotations/{annotation_id}",
        headers=headers,
    )
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_multi_tenant_annotation_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers1, project1, _, table1, _ = await setup_test_context(db_session, "owner1@test.com")
    _, headers2, project2, _, _, _ = await setup_test_context(db_session, "owner2@test.com")

    # Owner 1 creates annotation
    create_res = await client.post(
        f"/api/v1/projects/{project1.id}/annotations",
        json={"target_type": "table", "schema_table_id": str(table1.id), "note": "Secret table note"},
        headers=headers1,
    )
    annotation_id = create_res.json()["data"]["id"]

    # Owner 2 tries to access Owner 1's annotation
    unauth_res = await client.get(
        f"/api/v1/projects/{project1.id}/annotations/{annotation_id}",
        headers=headers2,
    )
    assert unauth_res.status_code == 404
