# Implementation Plan: Projects API, Tenant DB Connection & Schema Introspection

## Overview
This plan implements the complete backend lifecycle for:
1. **Projects CRUD API (Phase 0a)**: Root multi-tenant entity owned by authenticated users, supporting pagination, updates, deletion, and strict user isolation.
2. **Tenant Database Connection Management (Phase 0b)**: Secure credential registration, Fernet encryption at rest, connectivity testing, safe engine lifecycle.
3. **Schema Introspection & Caching (Phase 1)**: Asynchronous non-blocking reflection via SQLAlchemy, normalized caching into platform DB (`schema_cache`, `schema_tables`, `schema_columns`), and schema exploration REST APIs.

---

## Architecture Decisions

1. **Strict 5-Tier Domain Structure (`AGENTS.md`)**:
   - `projects/`: Schemas, Repository, Service (`ProjectService`), Router (`router.py`).
   - `connections/`: Schemas, Repository, Manager (`ConnectionManager`), Service (`ConnectionService`), Router (`router.py`).
   - `schema_introspection/`: Schemas, Repository, Service (`SchemaIntrospectionService`), Router (`router.py`).
2. **Multi-Tenancy & Project Isolation**:
   - Every `Project` is owned by an active `User` (`owner_id`).
   - Every `Connection`, `SchemaCache`, `SchemaTable`, `SchemaColumn` is scoped by `project_id`.
   - Cross-user and cross-project boundaries are strictly verified on every request.
3. **Encryption & Security Guardrails**:
   - Target database credentials are encrypted with Fernet (`encrypt_secret`) before storing in PostgreSQL.
   - Plaintext credentials are never returned in responses and never logged.
4. **Standard Unified API Response**:
   - All endpoints return `ApiResponse[T]` or `ApiResponse[PaginatedData[T]]` using helper utilities `success_response()`, `paginated_response()`, and domain exceptions (`NotFoundException`, `ForbiddenException`, `BadRequestException`).
5. **Non-Blocking Asynchronous Reflection**:
   - SQLAlchemy `inspect()` runs inside worker threads via `conn.run_sync()`.

---

## Task Breakdown

### Phase 1: Projects API (Phase 0a)

#### Task 1: Projects Domain (Schemas, Repository, Service)
- **Description:** Implement `ProjectRepository` with `owner_id` scoping & pagination, and `ProjectService` with domain exceptions and ownership enforcement.
- **Acceptance criteria:**
  - [ ] `ProjectRepository` methods: `create(owner_id, data)`, `get_by_id(project_id, owner_id)`, `list_by_owner(owner_id, skip, limit)`, `update(project, data)`, `delete(project)`.
  - [ ] `ProjectService` implements business logic and domain exceptions (`NotFoundException`).
  - [ ] `get_project_service` dependency function created.
- **Verification:**
  - [ ] Unit tests pass for repository and service methods.
- **Dependencies:** None
- **Files likely touched:**
  - `backend/app/domain/projects/schemas.py`
  - `backend/app/domain/projects/repository.py`
  - `backend/app/domain/projects/services.py`
- **Estimated scope:** Medium (3 files)

#### Task 2: Projects REST Router & Application Mounting
- **Description:** Refactor `projects/router.py` to use `ApiResponse[ProjectResponse]`, `ApiResponse[PaginatedData[ProjectResponse]]`, `Pagination`, and `get_current_active_user`, and mount the router in `app/main.py`.
- **Acceptance criteria:**
  - [ ] `POST /api/v1/projects`: Creates a project for authenticated user (201 Created).
  - [ ] `GET /api/v1/projects`: Returns paginated list of projects owned by user (200 OK).
  - [ ] `GET /api/v1/projects/{project_id}`: Returns project details (200 OK).
  - [ ] `PATCH /api/v1/projects/{project_id}`: Updates project (200 OK).
  - [ ] `DELETE /api/v1/projects/{project_id}`: Deletes project (204 No Content).
  - [ ] Mounted under `/api/v1/projects` in `main.py`.
- **Verification:**
  - [ ] API tests for project CRUD, pagination, and cross-user isolation pass.
- **Dependencies:** Task 1
- **Files likely touched:**
  - `backend/app/domain/projects/router.py`
  - `backend/app/main.py`
  - `backend/tests/unit/domain/projects/test_projects.py`
- **Estimated scope:** Medium (3 files)

### Checkpoint: Projects API Complete
- [ ] Projects CRUD fully functional and tested
- [ ] Multi-tenant user isolation verified

---

### Phase 2: Connection Management (Phase 0b)

#### Task 3: Connection Domain Foundation (Schemas, Repository, Manager Enhancements)
- **Description:** Implement `ConnectionCreate`, `ConnectionUpdate`, `ConnectionResponse`, `ConnectionTestRequest`, `ConnectionTestResponse`, `ConnectionRepository`, and connection testing in `ConnectionManager`.
- **Acceptance criteria:**
  - [ ] Pydantic schemas defined with credential masking in response.
  - [ ] `ConnectionRepository` implements CRUD with project isolation.
  - [ ] `ConnectionManager` adds connectivity testing and engine cleanup.
- **Verification:**
  - [ ] Unit tests for repository and manager pass.
- **Dependencies:** Task 2
- **Files likely touched:**
  - `backend/app/domain/connections/schemas.py`
  - `backend/app/domain/connections/repository.py`
  - `backend/app/domain/connections/manager.py`
- **Estimated scope:** Medium (3 files)

#### Task 4: Connection Service & REST API Router
- **Description:** Build `ConnectionService` (encryption, connectivity verification, project ownership check) and `connections/router.py`.
- **Acceptance criteria:**
  - [ ] `POST /api/v1/projects/{project_id}/connections`: Create connection.
  - [ ] `GET /api/v1/projects/{project_id}/connections`: Get connection details.
  - [ ] `PATCH /api/v1/projects/{project_id}/connections`: Update connection.
  - [ ] `DELETE /api/v1/projects/{project_id}/connections`: Delete connection and dispose engine.
  - [ ] `POST /api/v1/projects/{project_id}/connections/test`: Test connection credentials.
  - [ ] Mounted in `main.py`.
- **Verification:**
  - [ ] Unit and API tests for connection routes pass.
- **Dependencies:** Task 3
- **Files likely touched:**
  - `backend/app/domain/connections/services.py`
  - `backend/app/domain/connections/router.py`
  - `backend/app/main.py`
  - `backend/tests/unit/domain/connections/test_connections.py`
- **Estimated scope:** Medium (4 files)

### Checkpoint: Connection Management Complete
- [ ] Connection endpoints functional and verified
- [ ] Fernet encryption active and credentials never returned

---

### Phase 3: Schema Introspection & Caching (Phase 1)

#### Task 5: Schema Introspection Engine & Schemas
- **Description:** Define table/column introspection schemas and implement non-blocking reflection logic in `ConnectionManager`.
- **Acceptance criteria:**
  - [ ] `ColumnResponse`, `TableResponse`, `TableDetailResponse`, `SchemaOverviewResponse`, `IntrospectResponse` defined.
  - [ ] Reflection logic extracts tables, column types, nullability, PKs, and FKs.
- **Verification:**
  - [ ] Unit tests for introspection extraction against test DB.
- **Dependencies:** Task 4
- **Files likely touched:**
  - `backend/app/domain/schema_introspection/schemas.py`
  - `backend/app/domain/connections/manager.py`
- **Estimated scope:** Small-to-Medium (2 files)

#### Task 6: Schema Introspection Repository & Service
- **Description:** Build `SchemaIntrospectionRepository` and `SchemaIntrospectionService` to orchestrate schema reflection, atomic persistence in `schema_cache`, `schema_tables`, and `schema_columns`, and cache queries.
- **Acceptance criteria:**
  - [ ] `SchemaIntrospectionRepository` handles persistence and retrieval of `SchemaCache`, `SchemaTable`, `SchemaColumn`.
  - [ ] `SchemaIntrospectionService` coordinates reflection, database caching, and data retrieval.
- **Verification:**
  - [ ] Unit tests for introspection repository and service pass.
- **Dependencies:** Task 5
- **Files likely touched:**
  - `backend/app/domain/schema_introspection/repository.py`
  - `backend/app/domain/schema_introspection/services.py`
- **Estimated scope:** Medium (2 files)

#### Task 7: Schema Introspection REST Router & Application Wiring
- **Description:** Implement `schema_introspection/router.py` and mount in `main.py`.
- **Acceptance criteria:**
  - [ ] `POST /api/v1/projects/{project_id}/schema/introspect`: Trigger reflection & caching.
  - [ ] `GET /api/v1/projects/{project_id}/schema`: Retrieve schema overview.
  - [ ] `GET /api/v1/projects/{project_id}/schema/tables`: List tables.
  - [ ] `GET /api/v1/projects/{project_id}/schema/tables/{table_name}`: Get table details.
  - [ ] End-to-end integration tests verifying the full flow: Register User -> Create Project -> Add Connection -> Introspect Schema -> Query Tables & Columns.
  - [ ] `ruff check .` and `pyright` pass with 0 errors.
- **Verification:**
  - [ ] `pytest backend/tests` passes 100%.
- **Dependencies:** Task 6
- **Files likely touched:**
  - `backend/app/domain/schema_introspection/router.py`
  - `backend/app/main.py`
  - `backend/tests/integration/test_projects_connections_schema.py`
- **Estimated scope:** Medium-to-Large (3 files)

### Checkpoint: Complete Verification
- [ ] All tests passing
- [ ] Ruff & Pyright clean
- [ ] End-to-end verified
