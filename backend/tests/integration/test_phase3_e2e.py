"""
End-to-End Integration Test for Phase 3:
Register User -> Login -> Create Project -> Add Database Connection -> Introspect Schema -> Query Overview & Table Metadata.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.domain.schema_introspection.models import SchemaCache, SchemaTable


async def setup_target_e2e_database(db_path: str) -> None:
    """Setup a sample multi-table schema with primary keys, foreign keys, and nullability constraints."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(100) NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                );
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT,
                    published_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    author_name VARCHAR(100) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                );
                """
            )
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_phase3_e2e_journey(
    client: AsyncClient, db_session: AsyncSession, tmp_path: Any
) -> None:
    # Step 1: Register a new user
    user_email = f"e2e_user_{uuid.uuid4().hex[:6]}@example.com"
    user_password = "Pass1234"

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": user_password},
    )
    assert reg_res.status_code == 201
    reg_body = reg_res.json()
    assert reg_body["success"] is True
    assert reg_body["data"]["email"] == user_email

    # Step 2: Login to acquire JWT token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": user_password},
    )
    assert login_res.status_code == 200
    login_body = login_res.json()
    assert login_body["success"] is True
    token = login_body["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: Create a new project
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "E2E Schema Project", "description": "Phase 3 Introspection Test"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    project_data = proj_res.json()["data"]
    project_id = uuid.UUID(project_data["id"])

    # Step 4: Create target SQLite DB and add connection
    target_db_file = tmp_path / "e2e_target.db"
    await setup_target_e2e_database(str(target_db_file))
    target_conn_str = f"sqlite+aiosqlite:///{target_db_file}"

    conn_res = await client.post(
        f"/api/v1/projects/{project_id}/connections",
        json={
            "name": "E2E Target Database",
            "dialect": "sqlite",
            "connection_string": target_conn_str,
        },
        headers=headers,
    )
    assert conn_res.status_code == 201
    conn_body = conn_res.json()
    assert conn_body["success"] is True
    connection_id = uuid.UUID(conn_body["data"]["id"])

    # Step 5: Trigger live schema introspection
    intro_res = await client.post(
        f"/api/v1/projects/{project_id}/schema/introspect",
        headers=headers,
    )
    assert intro_res.status_code == 200
    intro_body = intro_res.json()
    assert intro_body["success"] is True
    assert intro_body["message"] == "Schema introspection completed successfully"

    intro_data = intro_body["data"]
    assert intro_data["table_count"] == 3
    assert intro_data["column_count"] == 14  # users:4, posts:5, comments:5

    # Step 6: Query high-level schema overview
    overview_res = await client.get(
        f"/api/v1/projects/{project_id}/schema",
        headers=headers,
    )
    assert overview_res.status_code == 200
    overview_body = overview_res.json()
    assert overview_body["success"] is True
    overview_data = overview_body["data"]
    assert overview_data["table_count"] == 3
    assert len(overview_data["tables"]) == 3

    # Step 7: List all tables and column metadata
    tables_res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables",
        headers=headers,
    )
    assert tables_res.status_code == 200
    tables_data = tables_res.json()["data"]
    assert len(tables_data) == 3

    table_by_name = {t["table_name"]: t for t in tables_data}
    assert "users" in table_by_name
    assert "posts" in table_by_name
    assert "comments" in table_by_name

    # Step 8: Query single table detail for "posts"
    posts_res = await client.get(
        f"/api/v1/projects/{project_id}/schema/tables/posts",
        headers=headers,
    )
    assert posts_res.status_code == 200
    posts_data = posts_res.json()["data"]
    assert posts_data["table_name"] == "posts"

    # Verify foreign key constraint on posts.user_id -> users.id
    user_id_col = next(c for c in posts_data["columns"] if c["column_name"] == "user_id")
    assert user_id_col["is_foreign_key"] is True
    assert user_id_col["fk_target_table"] == "users"

    # Step 9: Verify platform DB direct persistence
    stmt = (
        select(SchemaCache)
        .where(SchemaCache.project_id == project_id)
        .options(selectinload(SchemaCache.tables).selectinload(SchemaTable.columns))
    )
    result = await db_session.execute(stmt)
    cache_in_db = result.scalar_one_or_none()
    assert cache_in_db is not None
    assert cache_in_db.connection_id == connection_id
    assert "tables" in cache_in_db.raw_schema
    assert len(cache_in_db.tables) == 3
