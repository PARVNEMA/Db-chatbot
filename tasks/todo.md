# Todo: Projects API, Tenant DB Connection & Schema Introspection

## Phase 1: Projects API (Phase 0a)
- [x] **Task 1: Projects Domain (Schemas, Repository, Service)**
  - [x] Refine `ProjectCreate`, `ProjectUpdate`, `ProjectResponse` in `projects/schemas.py`
  - [x] Implement `ProjectRepository` in `projects/repository.py` with `owner_id` scoping and pagination
  - [x] Implement `ProjectService` in `projects/services.py` with domain exceptions (`NotFoundException`) and `get_project_service`
  - [x] Unit tests for project repository and service
- [x] **Task 2: Projects REST Router & Application Mounting**
  - [x] Implement `projects/router.py` with `ApiResponse[ProjectResponse]`, `ApiResponse[PaginatedData[ProjectResponse]]`, `Pagination`, and `get_current_active_user`
  - [x] Mount projects router in `app/main.py`
  - [x] Unit and API tests for projects CRUD, pagination, and user isolation

## Checkpoint: Projects API Complete
- [x] Projects CRUD fully functional and tested
- [x] User isolation and pagination verified

## Phase 2: Connection Management (Phase 0b)
- [x] **Task 3: Connection Domain Foundation (Schemas, Repository, Manager Enhancements)**
  - [x] Add `ConnectionCreate`, `ConnectionUpdate`, `ConnectionResponse`, `ConnectionTestRequest`, `ConnectionTestResponse` in `connections/schemas.py`
  - [x] Implement `ConnectionRepository` in `connections/repository.py` with `project_id` scoping
  - [x] Add connectivity test and engine disposal in `connections/manager.py`
  - [x] Unit tests for connection repository and manager
- [x] **Task 4: Connection Service & REST API Router**
  - [x] Implement `ConnectionService` in `connections/services.py` (Fernet encryption, project ownership validation, connection testing)
  - [x] Implement `connections/router.py` with `POST`, `GET`, `PATCH`, `DELETE`, and `POST /test`
  - [x] Mount connections router in `app/main.py`
  - [x] Unit & API tests for connection routes

## Checkpoint: Connection Management Complete
- [x] Connection endpoints functional and verified
- [x] Fernet encryption active and credentials never returned

## Phase 3: Schema Introspection & Caching (Phase 1)
- [ ] **Task 5: Schema Introspection Engine & Schemas**
  - [ ] Define `ColumnResponse`, `TableResponse`, `TableDetailResponse`, `SchemaOverviewResponse`, `IntrospectResponse` in `schema_introspection/schemas.py`
  - [ ] Implement async reflection engine using `conn.run_sync(inspect)` in `connections/manager.py` / introspection service
  - [ ] Test schema reflection extracting tables, column data types, nullability, PKs, and FKs
- [ ] **Task 6: Schema Introspection Repository & Service**
  - [ ] Implement `SchemaIntrospectionRepository` for `SchemaCache`, `SchemaTable`, `SchemaColumn` CRUD
  - [ ] Implement `SchemaIntrospectionService` (fetch connection, introspect, atomically save normalized schema + JSON cache)
  - [ ] Add cache refresh & table/column query methods
  - [ ] Unit tests for introspection repository and service
- [ ] **Task 7: Schema Introspection REST Router & Application Wiring**
  - [ ] Implement `schema_introspection/router.py` (`POST /introspect`, `GET /`, `GET /tables`, `GET /tables/{table_name}`)
  - [ ] Mount schema router in `main.py`
  - [ ] End-to-end integration tests covering: Register User -> Create Project -> Add Connection -> Introspect Schema -> Query Tables & Columns
  - [ ] Verify with `ruff check .`, `pyright`, and `pytest`

## Checkpoint: Complete Verification
- [ ] All unit and integration tests passing
- [ ] Linter & type checks clean
- [ ] Ready for user review / Phase 2 (Semantic Layer)
