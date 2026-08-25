# AI Agent Guidelines & Coding Standards for Backend

This document establishes mandatory coding standards, architectural rules, and behavior guidelines for all AI agents working on this codebase especially backend.

---

## 1. Domain-Driven Modular Architecture

All backend features are organized under `backend/app/domain/<module_name>/`. Every domain module follows a strict 5-tier layer separation:

### 1.1 Layer Responsibilities

1. **Routers (`router.py`)**:
   - **Role**: Thin HTTP controllers only.
   - **Allowed**: Route path/method declarations, FastAPI dependency injection, request payload validation, status codes, and returning Pydantic response models wrapped in `ApiResponse`.
   - **Forbidden**: Placing business logic, direct database queries, or raw SQL inside route handlers.
   - **Rule**: Every route handler must delegate execution immediately to a Domain Service.

2. **Services (`services.py`)**:
   - **Role**: Business logic, workflow orchestration, transaction boundaries, and domain validations.
   - **Rule**: Domain operations and multi-step workflows reside here. Services interact with Repositories for data access.

3. **Repositories (`repository.py`)**:
   - **Role**: Data access layer.
   - **Rule**: Extend `CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]` from `app.crud.base` for standard operations. Custom queries must use SQLAlchemy 2.0 `select()` syntax and always enforce multi-tenant filters (`project_id`).

4. **Schemas (`schemas.py`)**:
   - **Role**: Pydantic v2 schemas for request validation, response serialization, and domain DTOs.
   - **Rule**: Set `model_config = ConfigDict(from_attributes=True)` on response schemas returning ORM objects. Use explicit field types and validations.

5. **Models (`models.py`)**:
   - **Role**: Declarative SQLAlchemy ORM entities.
   - **Rule**: Inherit from `Base` and standard mixins (`TimestampMixin`, `UUIDPrimaryKeyMixin`) from `app.db.base`.

### 1.2 Inter-Domain Communication Boundaries

- **Direct Cross-Domain DB/Model Access Prohibited**: Never import or query another domain's ORM model or repository directly.
- **Service-to-Service Interaction**: If Domain A requires functionality or data from Domain B, it must invoke Domain B's public Service method or consume a shared interface defined in `app/core/`.

### 1.3 Strict Multi-Tenant Isolation

- Every database query, vector search, schema cache lookup, and chat session **MUST** be explicitly scoped by `project_id`.
- Never execute queries or mutations without explicit `where(Model.project_id == project_id)` filtering.

---

## 2. Standard Unified API Response Envelope

All API endpoints — whether returning single objects, paginated collections, or encountering errors — **MUST** conform to the unified response envelope defined in `app.core.responses`.

### 2.1 Envelope Schema

**Single Resource Success Response**:
```json
{
  "success": true,
  "message": "Project created successfully",
  "data": {
    "id": "c1f7b0be-0985-48ef-8fa4-106b8e8fba10",
    "name": "E-Commerce Analytics",
    "created_at": "2026-08-25T15:30:00Z"
  },
  "error": null
}
```

**Paginated Collection Success Response** (paginated payload lives strictly inside `data`):
```json
{
  "success": true,
  "message": "Projects retrieved successfully",
  "data": {
    "items": [
      {
        "id": "c1f7b0be-0985-48ef-8fa4-106b8e8fba10",
        "name": "E-Commerce Analytics"
      },
      {
        "id": "8a23d4e1-2311-41fa-9fa1-20984ba219a3",
        "name": "Customer Support Insights"
      }
    ],
    "total": 42,
    "skip": 0,
    "limit": 20
  },
  "error": null
}
```

**Error Response**:
```json
{
  "success": false,
  "message": "Resource not found",
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": null
  }
}
```

### 2.2 Reusable Response Utilities (`app.core.responses` / `app.core`)

| Utility | Type / Signature | Usage |
| :--- | :--- | :--- |
| `ApiResponse[T]` | `Generic[T]` Pydantic model | Outer response envelope model for route contracts: `@router.get("", response_model=ApiResponse[ProjectResponse])`. |
| `PaginatedData[T]` | `Generic[T]` Pydantic model | Paginated payload container with fields `items: list[T]`, `total: int`, `skip: int`, `limit: int`. Used as the generic argument: `ApiResponse[PaginatedData[T]]`. |
| `success_response(data, message)` | Helper function | Returns dict matching `ApiResponse` envelope: `return success_response(data=project, message="Project created")`. |
| `paginated_response(items, total, skip, limit, message)` | Helper function | Returns dict matching `ApiResponse[PaginatedData[T]]` envelope with pagination fields wrapped inside `data`. |
| `error_response(code, message, details)` | Helper function | Returns dict matching `ApiResponse` error structure. |

### 2.3 Router Implementation Examples

**Single Resource Endpoint**:
```python
from app.core.responses import ApiResponse, success_response
from app.domain.projects.schemas import ProjectResponse

@router.post("", response_model=ApiResponse[ProjectResponse], status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[ProjectResponse]:
    project = await service.create_project(data=data, owner_id=current_user.id)
    return success_response(data=project, message="Project created successfully")
```

**Paginated Collection Endpoint**:
```python
from app.core.responses import ApiResponse, PaginatedData, paginated_response
from app.dependencies.pagination import Pagination

@router.get("", response_model=ApiResponse[PaginatedData[ProjectResponse]])
async def list_projects(
    pagination: Pagination,
    service: Annotated[ProjectService, Depends(get_project_service)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ApiResponse[PaginatedData[ProjectResponse]]:
    items, total = await service.list_projects(owner_id=current_user.id, pagination=pagination)
    return paginated_response(
        items=items,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        message="Projects retrieved successfully",
    )
```

---

## 3. Reusable Core Components & Utilities

Agents must always reuse existing platform utilities rather than reimplementing ad-hoc solutions:

| Concern | Reusable Component / Location | Usage Rule |
| :--- | :--- | :--- |
| **Responses** | `app.core.responses.ApiResponse` / `success_response` | Wrap all endpoint outputs in `ApiResponse[T]` with standard `success`, `message`, `data`, `error` keys. |
| **Settings & Config** | `app.core.config.get_settings` / `settings` | Always load configuration via `get_settings()`. Never use `os.environ` or `os.getenv` directly in domain code. |
| **Exceptions & Errors** | `app.core.exceptions.*` | Always raise domain exceptions inheriting from `AppException` (`NotFoundException`, `BadRequestException`, `UnauthorizedException`, `ForbiddenException`, `ConflictException`, `ValidationException`). **Never** raise raw `fastapi.HTTPException`. |
| **Security & Crypto** | `app.core.security.*` | Use `encrypt_secret` / `decrypt_secret` for tenant DB credentials. Use `get_password_hash`, `verify_password`, `create_access_token`, and `verify_token` for auth. |
| **Logging** | `logging.getLogger(__name__)` | Use structured logging configured via `app.core.logging`. **Never** use `print()` statements. |
| **Generic CRUD** | `app.crud.base.CRUDBase` | Subclass `CRUDBase` in `repository.py` for reusable `get`, `get_multi`, `create`, `update`, `delete`, and `count` operations. |
| **ORM Base & Mixins** | `app.db.base.*` | Use `Base`, `TimestampMixin` (`id`, `created_at`, `updated_at`), or `UUIDPrimaryKeyMixin` for all database models. |
| **Dependencies** | `app.dependencies.*` | Use `DbSession`, `Pagination` / `PaginationParams`, `get_current_user`, `get_current_active_user`, `get_current_superuser`. |

---

## 4. FastAPI & Python Implementation Standards

1. **Dependency Injection**:
   - Always use `Annotated[..., Depends(...)]` for dependency injection signatures (e.g., `db: DbSession`, `pagination: Pagination`, `current_user: Annotated[User, Depends(get_current_active_user)]`).
   - Never manually instantiate database sessions in routers or services.

2. **Explicit Endpoint Contracts**:
   - Explicit `response_model=ApiResponse[...]` on every route decorator.
   - Use HTTP status code constants from `fastapi.status` (e.g., `status.HTTP_200_OK`, `status.HTTP_201_CREATED`, `status.HTTP_204_NO_CONTENT`).

3. **Pydantic v2 Conventions**:
   - Use `model_dump()`, `model_validate()`, `Field()`, and `ConfigDict`.
   - Avoid deprecated Pydantic v1 methods (`.dict()`, `.json()`, `class Config`).

4. **Async SQLAlchemy 2.0**:
   - Use `select(Model).where(...)` syntax exclusively. Legacy 1.x `session.query()` is forbidden.
   - Use `AsyncSession` injected via FastAPI dependency.
   - Never call blocking synchronous I/O methods inside `async def` routes. Sync I/O operations must run in worker threads via `anyio.to_thread.run_sync`.

5. **Type Safety & Code Quality**:
   - 100% type hint coverage on all function signatures, parameters, and return types.
   - Comply with Ruff formatting and Pyright type checking rules defined in `backend/pyproject.toml`.

---

## 5. Agent Behavior & Verification Rules

1. **Root Cause Fixes (No Superficial Patches)**:
   - When tests or runtime checks fail, identify and fix the underlying defect.
   - Never mask errors with silent `try/except: pass`, empty dummy fallbacks, or by commenting out assertions.

2. **Verification Before Declaring Completion**:
   - Always verify changes before completing tasks:
     - Run linting: `ruff check .`
     - Run type checking: `pyright`
     - Run automated test suite: `pytest`

3. **Security Guardrails**:
   - Target database credentials must always be encrypted using `encrypt_secret()` before persisting to platform database.
   - Never log raw passwords, decrypted connection strings, or unredacted tokens in application logs or exception tracebacks.
