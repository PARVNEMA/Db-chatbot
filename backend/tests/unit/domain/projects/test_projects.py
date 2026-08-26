"""
Unit and API integration tests for the Projects domain.

Tests:
- Project creation with user ownership.
- Multi-tenant isolation (User A cannot access User B's projects).
- Pagination support (total count, skip, limit).
- Project update and deletion.
- Standardized ApiResponse envelope validation.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.domain.auth.models import User
from app.domain.projects.schemas import ProjectCreate, ProjectUpdate
from app.domain.projects.services import ProjectService


async def create_test_user(
    db: AsyncSession, email: str = "test@example.com", is_active: bool = True
) -> tuple[User, dict[str, str]]:
    """Helper to insert a user and return the user object + auth headers."""
    user = User(
        email=email,
        hashed_password=get_password_hash("ValidPassword123!"),
        is_active=is_active,
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    return user, headers


@pytest.mark.asyncio
async def test_create_project_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await create_test_user(db_session, email="creator@example.com")

    payload = {
        "name": "E-Commerce Analytics",
        "description": "Production e-commerce database metrics",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Project created successfully"
    assert body["data"]["name"] == "E-Commerce Analytics"
    assert body["data"]["description"] == "Production e-commerce database metrics"
    assert body["data"]["owner_id"] == str(user.id)
    assert "id" in body["data"]
    assert body["error"] is None


@pytest.mark.asyncio
async def test_list_projects_multi_tenant_and_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user1, headers1 = await create_test_user(db_session, email="user1@example.com")
    user2, headers2 = await create_test_user(db_session, email="user2@example.com")

    # Create 3 projects for User 1
    for i in range(3):
        await client.post(
            "/api/v1/projects",
            json={"name": f"User1 Project {i}"},
            headers=headers1,
        )

    # Create 1 project for User 2
    await client.post(
        "/api/v1/projects",
        json={"name": "User2 Project"},
        headers=headers2,
    )

    # Fetch User 1 projects (default limit=20)
    res1 = await client.get("/api/v1/projects", headers=headers1)
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["success"] is True
    assert body1["data"]["total"] == 3
    assert len(body1["data"]["items"]) == 3
    for item in body1["data"]["items"]:
        assert item["owner_id"] == str(user1.id)

    # Test pagination (skip=0, limit=2)
    res_page = await client.get("/api/v1/projects?skip=0&limit=2", headers=headers1)
    assert res_page.status_code == 200
    page_body = res_page.json()
    assert page_body["data"]["total"] == 3
    assert len(page_body["data"]["items"]) == 2
    assert page_body["data"]["limit"] == 2
    assert page_body["data"]["skip"] == 0

    # Fetch User 2 projects
    res2 = await client.get("/api/v1/projects", headers=headers2)
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["data"]["total"] == 1
    assert len(body2["data"]["items"]) == 1
    assert body2["data"]["items"][0]["owner_id"] == str(user2.id)


@pytest.mark.asyncio
async def test_get_project_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await create_test_user(db_session, email="get_test@example.com")

    create_res = await client.post(
        "/api/v1/projects",
        json={"name": "Target Project", "description": "Target Desc"},
        headers=headers,
    )
    project_id = create_res.json()["data"]["id"]

    # Retrieve existing
    res = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["id"] == project_id
    assert body["data"]["name"] == "Target Project"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers = await create_test_user(db_session, email="notfound@example.com")
    fake_id = uuid.uuid4()

    res = await client.get(f"/api/v1/projects/{fake_id}", headers=headers)
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_project_cross_user_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user1, headers1 = await create_test_user(db_session, email="owner1@example.com")
    user2, headers2 = await create_test_user(db_session, email="owner2@example.com")

    create_res = await client.post(
        "/api/v1/projects",
        json={"name": "Private Project"},
        headers=headers1,
    )
    project_id = create_res.json()["data"]["id"]

    # User 2 attempts to access User 1's project -> should get 404
    res = await client.get(f"/api/v1/projects/{project_id}", headers=headers2)
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await create_test_user(db_session, email="updater@example.com")

    create_res = await client.post(
        "/api/v1/projects",
        json={"name": "Original Name", "description": "Original Desc"},
        headers=headers,
    )
    project_id = create_res.json()["data"]["id"]

    # Update name and description
    patch_res = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name", "description": "Updated Desc"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    body = patch_res.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Updated Name"
    assert body["data"]["description"] == "Updated Desc"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient, db_session: AsyncSession) -> None:
    user, headers = await create_test_user(db_session, email="deleter@example.com")

    create_res = await client.post(
        "/api/v1/projects",
        json={"name": "To Delete"},
        headers=headers,
    )
    project_id = create_res.json()["data"]["id"]

    # Delete
    del_res = await client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Subsequent GET returns 404
    get_res = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_project_service_direct(db_session: AsyncSession) -> None:
    user, _ = await create_test_user(db_session, email="service_user@example.com")
    service = ProjectService(db_session)

    # Create via service
    project = await service.create_project(
        data=ProjectCreate(name="Service Project", description="Service Desc"),
        owner_id=user.id,
    )
    assert project.id is not None
    assert project.name == "Service Project"

    # Get via service
    fetched = await service.get_project(project_id=project.id, owner_id=user.id)
    assert fetched.id == project.id

    # Update via service
    updated = await service.update_project(
        project_id=project.id,
        data=ProjectUpdate(name="Renamed Service Project"),
        owner_id=user.id,
    )
    assert updated.name == "Renamed Service Project"

    # Delete via service
    await service.delete_project(project_id=project.id, owner_id=user.id)
