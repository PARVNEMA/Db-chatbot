---
name: add-route
description: >
  Add a complete route to an existing domain module — from the router endpoint
  down through the service method, repository query, and Pydantic schema.
  Trigger when the user says "add route", "add endpoint", "add a GET/POST/PATCH/DELETE",
  or "implement <verb> <resource>".
disable-model-invocation: false
---

# Add Route — Full-Stack Implementation

Adds one HTTP endpoint to an existing domain module following the project's
domain-driven, layered architecture. Every step is mandatory; skip none.

## Prerequisite read

Before writing any code, read for a single target_module only :
1. `backend/app/domain/<target_module>/router.py` — existing route patterns.
2. `backend/app/domain/<target_module>/services.py` — existing service methods.
3. `backend/app/domain/<target_module>/repository.py` — existing query patterns.
4. `backend/app/domain/<target_module>/schemas.py` — existing schema classes.
5. `backend/app/domain/<target_module>/models.py` — ORM columns available.

This read phase is your completion criterion: you understand the module's existing
patterns before touching anything.

---

## Step 1 — Schema (schemas.py)

Add or extend schemas needed by the new endpoint.

**Request schema** (`Create` / `Update` / custom action body):
```python
class <Entity><Action>(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=255)
    optional_field: int | None = Field(default=None, gt=0)
```

**Response schema** (if a new one is needed):
```python
class <Entity>Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID          # always include for sub-resources
    field_name: str
    created_at: datetime
    updated_at: datetime
```

Rules enforced here:
- `ConfigDict(from_attributes=True)` on every response schema.
- `| None` union syntax, never `Optional[T]`.
- Never expose `encrypted_connection_string` or raw credentials in responses.
- `Update` schemas: all fields `| None` with `Field(default=None)`.

---

## Step 2 — Repository (repository.py)

Add the query method that the new service method will call.

```python
async def <method_name>(
    self,
    # Always include project_id for sub-resource queries
    project_id: uuid.UUID,
    # other params…
) -> <ReturnType>:
    result = await self._db.execute(
        select(<Model>).where(
            <Model>.project_id == project_id,  # ← MANDATORY for sub-resources
            # additional filters…
        ).order_by(<Model>.created_at.desc())
    )
    return result.scalar_one_or_none()   # or .scalars().all() for lists
```

Write operation pattern:
```python
async def create(self, project_id: uuid.UUID, payload: <Entity>Create) -> <Entity>:
    obj = <Entity>(project_id=project_id, **payload.model_dump())
    self._db.add(obj)
    await self._db.flush()
    await self._db.refresh(obj)
    return obj
```

Delete pattern:
```python
async def delete(self, obj: <Entity>) -> None:
    await self._db.delete(obj)
    await self._db.flush()
```

Rules enforced here:
- SQLAlchemy 2.0 `select(Model).where(...)` — never `session.query()`.
- `project_id` filter in **every** query touching a sub-resource.
- `flush()` + `refresh()` on writes; **never** `commit()` inside a repository.
- `model_dump(exclude_unset=True)` for partial `Update` payloads.

---

## Step 3 — Service (services.py)

Add the service method that orchestrates the repository call and applies business rules.

```python
async def <method_name>(
    self,
    project_id: uuid.UUID,
    # other params…
) -> <ReturnType>:
    # Validation / 404 check
    entity = await self._repo.get_by_id(entity_id, project_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"<Entity> {entity_id} not found.",
        )
    # Delegate to repository
    return await self._repo.<repo_method>(project_id, payload)
```

Rules enforced here:
- Raise `HTTPException` from the service, **never** from the router or repository.
- Use `status.HTTP_<N>` constants, never raw integers.
- Every 404 check goes through a dedicated `get_<entity>_or_404` method.
- Prefer existing `app/core/exceptions.py` types (`NotFoundException`, etc.) for non-HTTP scenarios.
- Pass `project_id` through from the caller — never query without it on sub-resources.

---

## Step 4 — Router (router.py)

Add the thin route handler that wires the HTTP verb to the service.

```python
@router.<method>(
    "/<path>",
    response_model=<Schema>,
    status_code=status.HTTP_<N>,
)
async def <handler_name>(
    project_id: uuid.UUID,            # path param for sub-resources
    payload: <RequestSchema>,         # body — omit for GET/DELETE
    service: Annotated[<Service>, Depends()],
) -> <Schema>:
    result = await service.<method_name>(project_id, payload)
    return <Schema>.model_validate(result)
```

HTTP verb → status code reference:
| Verb   | Success status               |
|--------|------------------------------|
| POST   | `HTTP_201_CREATED`           |
| GET    | `HTTP_200_OK` (default)      |
| PATCH  | `HTTP_200_OK` (default)      |
| DELETE | `HTTP_204_NO_CONTENT`        |

Rules enforced here:
- `response_model=` is mandatory on every route decorator.
- `Annotated[Service, Depends()]` — no bare `Depends()` as a default argument.
- Handler body: one service call + one `model_validate` call. Nothing else.
- DELETE handlers return `None` (status 204 sends no body).

---

## Step 5 — Register in main.py (new domain only)

Skip this step if the domain router is already registered.

Add inside `create_app()` in `backend/app/main.py`:

```python
from app.domain.<module>.router import router as <module>_router

app.include_router(
    <module>_router,
    prefix=f"{settings.API_V1_PREFIX}/<plural-resource>",
    tags=["<module>"],
)
```

---

## Step 6 — Verify

Run all checks from `backend/` before declaring done:

```bash
ruff check .       # zero lint errors
ruff format .      # auto-format applied
pyright            # zero type errors
pytest             # all tests green
```

Completion criterion: **all four commands exit 0**. Do not stop until they do.
