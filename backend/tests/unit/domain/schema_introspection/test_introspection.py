"""
Unit tests for Schema Introspection domain.

Covers:
- Async database schema reflection (tables, columns, types, PKs, FKs).
- SchemaIntrospectionRepository CRUD and atomic persistence.
- SchemaIntrospectionService workflows (introspection, overview, listing, table details).
- FastAPI REST API endpoints (/schema/introspect, /schema, /schema/tables, /schema/tables/{table_name}).
- Multi-tenant user and project isolation.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.security import create_access_token, get_password_hash
from app.domain.auth.models import User
from app.domain.projects.schemas import ProjectCreate
from app.domain.projects.services import ProjectService


async def create_test_user_and_project(
    db: AsyncSession, email: str = "schema_user@example.com"
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
        data=ProjectCreate(name="Schema Test Project"),
        owner_id=user.id,
    )
    return user, headers, project.id


async def setup_target_database_with_schema(db_path: str) -> None:
    """Populate a temporary SQLite database with customers, orders, and order_items tables."""
    target_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with target_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    total_amount NUMERIC(10, 2) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                );
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_name VARCHAR(200) NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price NUMERIC(10, 2) NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                );
                """
            )
        )
    await target_engine.dispose()


@pytest.mark.asyncio
async def test_introspect_schema_endpoint(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    # 1. Setup target DB
    target_db_file = tmp_path / "test_target.db"
    await setup_target_database_with_schema(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    # 2. Setup user and project
    user, headers, project_id = await create_test_user_and_project(
        db_session, email="intro_user@example.com"
    )

    # 3. Create Connection
    conn_res = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "E-Commerce DB",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers,
    )
    assert conn_res.status_code == 201

    # 4. Trigger Schema Introspection
    intro_res = await client.post(
        f"/api/v1/projects/{project_id}/schema/introspect",
        headers=headers,
    )
    assert intro_res.status_code == 200
    intro_body = intro_res.json()
    assert intro_body["success"] is True
    assert intro_body["message"] == "Schema introspection completed successfully"

    data = intro_body["data"]
    assert data["project_id"] == str(project_id)
    assert data["table_count"] == 3
    assert data["column_count"] == 13  # 4 + 4 + 5

    # Verify tables detail in response
    table_names = [t["table_name"] for t in data["tables"]]
    assert "customers" in table_names
    assert "orders" in table_names
    assert "order_items" in table_names

    # Check orders table columns & foreign keys
    orders_table = next(t for t in data["tables"] if t["table_name"] == "orders")
    customer_id_col = next(
        c for c in orders_table["columns"] if c["column_name"] == "customer_id"
    )
    assert customer_id_col["is_foreign_key"] is True
    assert customer_id_col["fk_target_table"] == "customers"

    # 5. Check GET /schema (Overview)
    overview_res = await client.get(
        f"/api/v1/projects/{project_id}/schema",
        headers=headers,
    )
    assert overview_res.status_code == 200
    overview_data = overview_res.json()["data"]
    assert overview_data["table_count"] == 3
    assert len(overview_data["tables"]) == 3

    # 6. Check GET /schema/tables
    tables_res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables",
        headers=headers,
    )
    assert tables_res.status_code == 200
    tables_data = tables_res.json()["data"]
    assert len(tables_data) == 3

    # 7. Check GET /schema/tables/{table_name}
    single_table_res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables/customers",
        headers=headers,
    )
    assert single_table_res.status_code == 200
    cust_data = single_table_res.json()["data"]
    assert cust_data["table_name"] == "customers"
    assert len(cust_data["columns"]) == 4

    id_col = next(c for c in cust_data["columns"] if c["column_name"] == "id")
    assert id_col["is_primary_key"] is True


@pytest.mark.asyncio
async def test_get_schema_before_introspection_returns_404(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    target_db_file = tmp_path / "empty_target.db"
    await setup_target_database_with_schema(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    _, headers, project_id = await create_test_user_and_project(
        db_session, email="no_intro@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "Unintrospected DB",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers,
    )

    res = await client.get(f"/api/v1/projects/{project_id}/schema", headers=headers)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SCHEMA_NOT_INTROSPECTED"


@pytest.mark.asyncio
async def test_get_nonexistent_table_returns_404(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    target_db_file = tmp_path / "target_404.db"
    await setup_target_database_with_schema(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    _, headers, project_id = await create_test_user_and_project(
        db_session, email="notable_user@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "DB 404",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers,
    )

    await client.post(
        f"/api/v1/projects/{project_id}/schema/introspect",
        headers=headers,
    )

    res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables/non_existent_table",
        headers=headers,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "TABLE_NOT_FOUND"


@pytest.mark.asyncio
async def test_schema_cross_user_isolation(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    target_db_file = tmp_path / "isolation_target.db"
    await setup_target_database_with_schema(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    _, headers1, project1_id = await create_test_user_and_project(
        db_session, email="owner_user@example.com"
    )
    _, headers2, _ = await create_test_user_and_project(
        db_session, email="attacker_user@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project1_id}/connections",
        json={
            "name": "Owner DB",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers1,
    )

    await client.post(
        f"/api/v1/projects/{project1_id}/schema/introspect",
        headers=headers1,
    )

    # Attacker tries to access Owner's schema -> 404
    res = await client.get(
        f"/api/v1/projects/{project1_id}/schema",
        headers=headers2,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_schema_reintrospection_refreshes_atomically(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    target_db_file = tmp_path / "refresh_target.db"
    await setup_target_database_with_schema(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    _, headers, project_id = await create_test_user_and_project(
        db_session, email="refresh_user@example.com"
    )

    await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "Refresh DB",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers,
    )

    # First introspection: 3 tables
    res1 = await client.post(
        f"/api/v1/projects/{project_id}/schema/introspect",
        headers=headers,
    )
    assert res1.status_code == 200
    assert res1.json()["data"]["table_count"] == 3

    # Add a 4th table to target database
    target_engine = create_async_engine(target_conn_str)
    async with target_engine.begin() as conn:
        await conn.execute(
            text("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT NOT NULL);")
        )
    await target_engine.dispose()

    # Second introspection: should refresh to 4 tables
    res2 = await client.post(
        f"/api/v1/projects/{project_id}/schema/introspect",
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["table_count"] == 4

    # Verify query for products table
    prod_res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables/products",
        headers=headers,
    )
    assert prod_res.status_code == 200
    assert prod_res.json()["data"]["table_name"] == "products"
