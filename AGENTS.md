# AI Agent Guidelines & Coding Standards

This document establishes mandatory coding standards, architectural rules, and behavior guidelines for all AI agents working on this codebase.

---

## 1. Core Architectural Principles

1. **Domain-Driven Modular Architecture**:
   - All backend features live under `backend/app/domain/<module_name>/`.
   - Each domain directory is self-contained: `router.py`, `schemas.py`, `models.py`, `services.py`, `repository.py`.
   - Direct cross-module model or database access is strictly prohibited; inter-domain communication must happen through dedicated service boundaries or shared interfaces in `app/core/`.

2. **Strict Multi-Tenant Isolation**:
   - Every database query, schema cache operation, vector embedding search, and chat session **MUST** be scoped by `project_id`.
   - Never write single-tenant or global queries without explicit `project_id` filtering.

3. **Separation of Control Plane vs Data Plane**:
   - **Control Plane (Platform DB)**: PostgreSQL metadata database managed via Async SQLAlchemy 2.0 and Alembic (`app/core/db.py`).
   - **Data Plane (Tenant DBs)**: Dynamic target databases managed exclusively via `ConnectionManager` (`app/domain/connections/manager.py`) with read-only guardrails, execution timeouts, and row caps.

---

## 2. Python & FastAPI Standards

1. **FastAPI & Pydantic v2**:
   - Use Pydantic v2 (`from pydantic import BaseModel, ConfigDict, Field`).
   - Use `Annotated` for FastAPI dependency injection (e.g., `db: Annotated[AsyncSession, Depends(get_db)]`).
   - Explicit response models on every endpoint route (`response_model=...`).
   - Use `status` code constants from `fastapi.status`.

2. **Async SQLAlchemy 2.0**:
   - Use SQLAlchemy 2.0 style queries exclusively (`select(Model).where(...)`). Never use legacy 1.x `query()` syntax.
   - Use `AsyncSession` provided via FastAPI dependency injection.
   - Never call blocking synchronous I/O methods (e.g., `requests.get()`, synchronous SQLAlchemy drivers) inside `async def` route handlers. Use `httpx` or execute CPU/IO sync operations in thread pools (`anyio.to_thread.run_sync`).

3. **Type Safety & Linting**:
   - 100% type hint coverage on function signatures and return types.
   - Strict adherence to Ruff formatting and Pyright type checking rules defined in `backend/pyproject.toml`.

---

## 3. Agent Execution Guidelines

1. **No Superficial Symptom Patches**:
   - When an exception or test failure occurs, trace and fix the root cause.
   - Never mask errors with silent `try/except: pass`, empty dummy fallbacks, or by commenting out broken assertions.

2. **Verification Before Success**:
   - Always run linting (`ruff check`), type checking (`pyright`), and automated tests (`pytest`) before declaring completion.

3. **Security Rules**:
   - Connection strings **MUST** be encrypted using Fernet symmetric encryption before storing in the database.
   - Never log raw credentials, decrypted connection strings, or full API keys in application logs or tracebacks.
