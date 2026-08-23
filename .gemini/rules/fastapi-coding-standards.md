# FastAPI Coding Standards

Professional coding standards for the Natural Language Database Querying Platform backend.
These rules apply to all code under `backend/app/`.

---

## 1. Module Structure (Domain-Driven)

Every domain lives at `backend/app/domain/<module>/` with exactly these files:

```
<module>/
├── __init__.py       # empty or re-exports only
├── models.py         # SQLAlchemy ORM models
├── schemas.py        # Pydantic v2 request/response schemas
├── repository.py     # DB access — all queries live here
├── services.py       # Business logic — orchestrates repository
└── router.py         # FastAPI routes — thin, delegates to service
```

Cross-module access is **forbidden**. Shared interfaces go in `app/core/`.

---

## 2. Router Rules

- Every route **must** have `response_model=` and explicit `status_code=`.
- Use `status` constants from `fastapi.status`, never raw integers.
- Use `Annotated` for all dependency injections — no bare `Depends()` as a default.
- Route handlers are thin: one service call, one `model_validate`, return.
- Never raise `HTTPException` from a router — raise it from the service.
- Always scope sub-resources under their parent path prefix (e.g. `/projects/{project_id}/connections`).

```python
# ✅ Correct
@router.post("/", response_model=FooResponse, status_code=status.HTTP_201_CREATED)
async def create_foo(
    payload: FooCreate,
    service: Annotated[FooService, Depends()],
) -> FooResponse:
    foo = await service.create_foo(payload)
    return FooResponse.model_validate(foo)

# ❌ Wrong — missing response_model, raw 201, bare Depends
@router.post("/")
async def create_foo(payload: FooCreate, service=Depends(FooService)):
    return await service.create_foo(payload)
```

---

## 3. Service Rules

- Service classes receive dependencies via `__init__` using `Annotated[AsyncSession, Depends(get_db)]`.
- Services instantiate the repository; they never access `_db` directly.
- 404 lookups always go through a `get_<entity>_or_404` method that raises `HTTPException(status.HTTP_404_NOT_FOUND)`.
- Business validation raises `HTTPException` with appropriate status codes and `detail` strings.
- **Never** raise bare `Exception` — use the domain exceptions in `app/core/exceptions.py`.
- Multi-tenant: every service method that fetches tenant data **must** accept and pass `project_id`.

```python
# ✅ Correct service
class FooService:
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
        self._repo = FooRepository(db)

    async def get_foo_or_404(self, foo_id: uuid.UUID, project_id: uuid.UUID) -> Foo:
        foo = await self._repo.get_by_id(foo_id, project_id)
        if foo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Foo {foo_id} not found.")
        return foo
```

---

## 4. Repository Rules

- Repository `__init__` accepts only `AsyncSession` — **no** FastAPI `Depends()` here.
- All queries use SQLAlchemy 2.0 style: `select(Model).where(...)`. Never use legacy `session.query()`.
- Every query on a sub-resource **must** include a `project_id` filter in the `WHERE` clause.
- Use `await session.execute(...)` and `.scalar_one_or_none()` / `.scalars().all()`.
- Write operations use `session.add()` + `await session.flush()` + `await session.refresh(obj)`.
- Delete uses `await session.delete(obj)` + `await session.flush()`.
- **Never commit** inside a repository — the session commit is managed by the unit-of-work middleware.

```python
# ✅ Correct — project_id scoped
async def get_by_id(self, foo_id: uuid.UUID, project_id: uuid.UUID) -> Foo | None:
    result = await self._db.execute(
        select(Foo).where(Foo.id == foo_id, Foo.project_id == project_id)
    )
    return result.scalar_one_or_none()

# ❌ Wrong — missing project_id scope
async def get_by_id(self, foo_id: uuid.UUID) -> Foo | None:
    result = await self._db.execute(select(Foo).where(Foo.id == foo_id))
    return result.scalar_one_or_none()
```

---

## 5. Schema Rules (Pydantic v2)

- Import: `from pydantic import BaseModel, ConfigDict, Field`.
- Response schemas **must** set `model_config = ConfigDict(from_attributes=True)`.
- Validate with `Model.model_validate(orm_object)`, never `Model.from_orm()`.
- Use `Field(...)` for required fields with constraints (`min_length`, `max_length`, `gt`, etc.).
- Input schemas (`Create`, `Update`) never expose encrypted or internal fields (e.g. `encrypted_connection_string`).
- `Update` schemas use `| None` + `Field(default=None)` for all optional patch fields.
- Use `model_dump(exclude_unset=True)` in repositories for partial updates.

```python
class FooCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: int = Field(..., gt=0)

class FooUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)

class FooResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
```

---

## 6. ORM Model Rules

- All models inherit from `app.db.base.Base`.
- Use `TimestampMixin` from `app.db.base` to get `id`, `created_at`, `updated_at` automatically.
- Sub-resource models **must** have a `project_id` column as a `ForeignKey` with `ondelete="CASCADE"`, indexed.
- Use `Mapped[T]` and `mapped_column(...)` — never use old-style `Column(...)`.
- `UUID` primary keys use `UUID(as_uuid=True)` with `default=uuid.uuid4`.
- Timestamps use `DateTime(timezone=True)` with `server_default=func.now()`.

```python
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

class Foo(Base):
    __tablename__ = "foos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

---

## 7. Type Safety Rules

- 100% type hint coverage on all function signatures and return types.
- Return types must be explicit — never omit `-> T`.
- Use `T | None` (union syntax, Python 3.10+), never `Optional[T]`.
- Avoid `Any` unless interfacing with untyped third-party libraries; document why with a comment.
- Run `pyright` in `standard` mode (configured in `pyrightconfig.json`) — zero errors before merging.

---

## 8. Async Rules

- All route handlers and service methods must be `async def`.
- **Never** call blocking synchronous I/O inside `async def`: no `requests.get()`, no sync SQLAlchemy drivers.
- Use `httpx.AsyncClient` for outbound HTTP.
- Offload CPU-bound or unavoidably synchronous work with `anyio.to_thread.run_sync(...)`.

---

## 9. Security Rules

- Connection strings **must** be encrypted with Fernet (`app.core.security.encrypt`) before `INSERT`.
- Decryption happens **only** inside `ConnectionManager` (`app/domain/connections/manager.py`).
- Raw credentials, decrypted strings, and API keys **must never** appear in logs or tracebacks.
- JWT secrets **must** come from `settings.JWT_SECRET_KEY` — never hardcoded.

---

## 10. Router Registration in `main.py`

When a new domain router is ready, register it in `app/main.py` inside `create_app()`:

```python
from app.domain.<module>.router import router as <module>_router
app.include_router(
    <module>_router,
    prefix=f"{settings.API_V1_PREFIX}/<plural-resource>",
    tags=["<module>"],
)
```

---

## 11. Linting & Formatting

Run before every commit (from `backend/`):

```bash
ruff check .          # zero errors
ruff format .         # auto-format
pyright               # zero type errors
pytest                # all tests green
```

Config lives in `pyproject.toml`: line length 100, Ruff rule sets E, W, F, I, C, B, UP.
