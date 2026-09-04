"""
Unit and API integration tests for the Embeddings domain.

Tests:
- Composite embed_text generation (structural schema + semantic descriptions).
- Embedding repository persistence and pgvector search.
- Schema vector search endpoint (`POST /api/v1/projects/{project_id}/schema/search`).
- Manual embedding generation trigger (`POST /api/v1/projects/{project_id}/schema/embeddings/generate`).
- LLM auto-suggest endpoint (`POST /api/v1/projects/{project_id}/schema/auto-suggest`).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.domain.auth.models import User
from app.domain.connections.models import Connection
from app.domain.embeddings.services import build_composite_embed_text
from app.domain.projects.models import Project
from app.domain.schema_introspection.models import SchemaCache, SchemaColumn, SchemaTable
from app.domain.semantic_layer.models import SchemaAnnotation


async def setup_embeddings_test_context(
    db: AsyncSession, email: str = "embedder@example.com"
) -> tuple[User, dict[str, str], Project, Connection, SchemaTable, SchemaColumn]:
    """Helper to set up test user, project, connection, table, and columns."""
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
        name="Vector Search Analytics",
        description="Testing schema embeddings",
        owner_id=user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    connection = Connection(
        project_id=project.id,
        name="Production DB",
        dialect="postgresql",
        encrypted_connection_string="gAAAAABtest_encrypted",
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
        table_name="orders",
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)

    column1 = SchemaColumn(
        table_id=table.id,
        project_id=project.id,
        connection_id=connection.id,
        column_name="total_amount",
        data_type="NUMERIC(10,2)",
        ordinal_position=1,
    )
    column2 = SchemaColumn(
        table_id=table.id,
        project_id=project.id,
        connection_id=connection.id,
        column_name="customer_id",
        data_type="UUID",
        is_foreign_key=True,
        fk_target_table="customers",
        fk_target_column="id",
        ordinal_position=2,
    )
    db.add_all([column1, column2])
    await db.commit()
    await db.refresh(column1)
    await db.refresh(column2)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    return user, headers, project, connection, table, column1


def test_build_composite_embed_text() -> None:
    """Test composite string generation fusing structural and semantic properties."""
    table = SchemaTable(
        id=uuid.uuid4(),
        cache_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        schema_name="public",
        table_name="orders",
    )
    col1 = SchemaColumn(
        id=uuid.uuid4(),
        table_id=table.id,
        project_id=table.project_id,
        connection_id=table.connection_id,
        column_name="total_amount",
        data_type="NUMERIC(10,2)",
        is_nullable=False,
        is_primary_key=False,
        ordinal_position=1,
    )
    table.columns = [col1]

    t_annot = SchemaAnnotation(
        id=uuid.uuid4(),
        project_id=table.project_id,
        connection_id=table.connection_id,
        target_type="table",
        note="Stores customer purchase transactions",
    )
    c_annot = SchemaAnnotation(
        id=uuid.uuid4(),
        project_id=table.project_id,
        connection_id=table.connection_id,
        target_type="column",
        note="Total revenue generated from order including tax and shipping",
    )

    text = build_composite_embed_text(
        column=col1,
        table=table,
        table_annotations=[t_annot],
        column_annotations=[c_annot],
    )

    assert "Total revenue generated from order including tax and shipping" in text
    assert "total_amount" in text
    assert "NUMERIC(10,2)" in text
    assert "public.orders table" in text
    assert "Stores customer purchase transactions" in text


@pytest.mark.asyncio
async def test_generate_embeddings_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /{project_id}/schema/embeddings/generate."""
    _, headers, project, _, _, _ = await setup_embeddings_test_context(
        db_session, "gen_test@test.com"
    )

    from app.core.config import get_settings
    settings = get_settings()
    dim = settings.EMBEDDING_DIMENSIONS

    mock_embeddings_client = MagicMock()
    mock_embeddings_client.embed_documents.return_value = [
        [0.1] * dim,
        [0.2] * dim,
    ]

    with patch("app.domain.embeddings.services.get_embeddings_client", return_value=mock_embeddings_client):
        response = await client.post(
            f"/api/v1/projects/{project.id}/schema/embeddings/generate",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["embedded_columns_count"] == 2
        assert body["data"]["dimensions"] == dim


@pytest.mark.asyncio
async def test_search_schema_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /{project_id}/schema/search."""
    _, headers, project, _, _, _ = await setup_embeddings_test_context(
        db_session, "search_test@test.com"
    )

    from app.core.config import get_settings
    settings = get_settings()
    dim = settings.EMBEDDING_DIMENSIONS

    mock_embeddings_client = MagicMock()
    mock_embeddings_client.embed_documents.return_value = [[0.1] * dim, [0.2] * dim]
    mock_embeddings_client.embed_query.return_value = [0.15] * dim

    with patch("app.domain.embeddings.services.get_embeddings_client", return_value=mock_embeddings_client):
        # 1. Generate embeddings first
        await client.post(
            f"/api/v1/projects/{project.id}/schema/embeddings/generate",
            headers=headers,
        )

        # 2. Search
        search_payload = {
            "query": "How much revenue or total sales did we make?",
            "top_k": 5,
        }
        res = await client.post(
            f"/api/v1/projects/{project.id}/schema/search",
            json=search_payload,
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]) > 0
        assert body["data"][0]["table_name"] == "orders"


@pytest.mark.asyncio
async def test_auto_suggest_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /{project_id}/schema/auto-suggest with compulsory table_id."""
    _, headers, project, _, table, _ = await setup_embeddings_test_context(
        db_session, "autosuggest_test@test.com"
    )

    from app.core.config import get_settings
    settings = get_settings()
    dim = settings.EMBEDDING_DIMENSIONS

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="""
```json
{
  "table_description": "Customer sales and purchase orders",
  "column_descriptions": {
    "total_amount": "Total price of the order in USD",
    "customer_id": "Foreign key reference to customers"
  }
}
```
"""
        )
    )

    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.return_value = [[0.1] * dim, [0.2] * dim]

    with (
        patch("app.domain.embeddings.services.get_llm_client", return_value=mock_llm),
        patch("app.domain.embeddings.services.get_embeddings_client", return_value=mock_embeddings),
    ):
        # 1. Success case with compulsory table_id
        response = await client.post(
            f"/api/v1/projects/{project.id}/schema/auto-suggest",
            json={"table_id": str(table.id)},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["table_id"] == str(table.id)
        assert body["data"]["table_name"] == "orders"
        assert body["data"]["table_description"] == "Customer sales and purchase orders"
        assert body["data"]["suggested_tables_count"] == 1
        assert body["data"]["suggested_columns_count"] == 2

        # 2. Missing table_id returns 422 Unprocessable Entity
        missing_payload_response = await client.post(
            f"/api/v1/projects/{project.id}/schema/auto-suggest",
            json={},
            headers=headers,
        )
        assert missing_payload_response.status_code == 422

        # 3. Non-existent table_id returns 404 Not Found
        random_table_id = str(uuid.uuid4())
        not_found_response = await client.post(
            f"/api/v1/projects/{project.id}/schema/auto-suggest",
            json={"table_id": random_table_id},
            headers=headers,
        )
        assert not_found_response.status_code == 404



@pytest.mark.asyncio
async def test_generate_embeddings_streaming_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /{project_id}/schema/embeddings/generate?stream=true."""
    _, headers, project, _, _, _ = await setup_embeddings_test_context(
        db_session, "sse_test@test.com"
    )

    from app.core.config import get_settings
    settings = get_settings()
    dim = settings.EMBEDDING_DIMENSIONS

    mock_embeddings_client = MagicMock()
    mock_embeddings_client.embed_documents.return_value = [
        [0.1] * dim,
        [0.2] * dim,
    ]

    with patch("app.domain.embeddings.services.get_embeddings_client", return_value=mock_embeddings_client):
        response = await client.post(
            f"/api/v1/projects/{project.id}/schema/embeddings/generate?stream=true",
            headers=headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert "event: start" in content
        assert "event: progress" in content
        assert "event: complete" in content
