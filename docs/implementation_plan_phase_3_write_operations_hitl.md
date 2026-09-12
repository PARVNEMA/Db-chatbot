# Phase 3 Plan: Safe INSERT/PATCH with HITL via WebSocket

## Summary

Add an approval-first write workflow to the chat agent. The current read-only pipeline remains unchanged; writes use a separate, fail-closed path for PostgreSQL and MySQL only.

The write flow operates over a **persistent WebSocket connection** (replacing the existing SSE `StreamingResponse`), enabling true bidirectional communication for the approval loop. The WebSocket carries both read-path streaming events _and_ the new write-path interactive HITL events — a single connection per chat session.

Write operations support **multi-table change-sets**: a single user request can produce INSERT and/or PATCH operations across multiple tables (e.g. "add a customer and create their first order"), with a **per-table row cap** and a **total row cap per change-set** enforced before approval.

Every change-set will:

1. Resolve write intent and identify target tables from cached schema metadata.
2. Build a structured multi-table mutation proposal (never executable raw LLM SQL).
3. Collect missing required fields through an interactive WebSocket prompt–response loop.
4. Validate deterministically, preview affected rows, and present the change-set.
5. Require project-owner approval via the WebSocket (or REST fallback).
6. Revalidate and execute atomically using parameterized SQL inside a single transaction.
7. Persist an encrypted audit record and return the outcome.

---

## 1. WebSocket Transport Layer

### 1.1 Why WebSocket over SSE

| Concern | SSE (current) | WebSocket (proposed) |
|---|---|---|
| Direction | Server → Client only | Full-duplex bidirectional |
| HITL prompts | Requires separate REST round-trips for user responses | User responds inline on the same connection |
| Approval flow | Client must POST to a separate endpoint | Client sends `approve` / `reject` frames directly |
| Missing-field collection | One REST call per missing field | Conversational back-and-forth on one socket |
| Auth token refresh | New connection per request | Single long-lived authenticated connection |
| Connection overhead | New HTTP connection per message send | Single persistent connection per session |
| Reconnection | Built-in `EventSource` retry | Must implement reconnect + replay (worth it) |

### 1.2 WebSocket Endpoint

```text
ws://host/api/v1/projects/{project_id}/chat/sessions/{session_id}/ws
```

- Authentication: JWT token passed as `?token=<jwt>` query parameter (WebSocket does not support custom headers). Validated during the `websocket.accept()` handshake. Reject with `4001` close code on auth failure.
- The WebSocket replaces the existing `POST .../messages` SSE endpoint for real-time streaming. The SSE endpoint remains available as a **deprecated fallback** for clients that cannot use WebSocket.
- Connection lifecycle: one WebSocket per chat session. The server holds the connection open and streams events for each user message. The client sends JSON frames for messages, field responses, and approval actions.

### 1.3 Wire Protocol

All frames are JSON with a mandatory `type` field.

**Client → Server frames:**

| `type` | Purpose | Key fields |
|---|---|---|
| `message` | Send a new user query | `content: string` |
| `field_response` | Reply to a missing-field prompt | `mutation_id: uuid`, `field: string`, `value: any` |
| `approve` | Approve a pending change-set | `mutation_id: uuid`, `idempotency_key: string` |
| `reject` | Reject a pending change-set | `mutation_id: uuid`, `reason?: string` |
| `ping` | Keep-alive | — |

**Server → Client frames (superset of existing SSE events):**

| `type` | Purpose |
|---|---|
| `message_received` | Echo of persisted user message |
| `intent_classified` | Intent + entities result |
| `sql_generated` | Generated SQL (reads) |
| `sql_executed` | Read query results |
| `summary_ready` | NL summary |
| `final_result` | Complete read result |
| `mutation_proposal` | Structured multi-table change-set preview |
| `mutation_field_required` | Prompt for a missing required field |
| `mutation_preview` | Row-level before/after preview per table |
| `mutation_approval_required` | Request owner approval |
| `mutation_approved` | Confirmation of approval |
| `mutation_rejected` | Confirmation of rejection |
| `mutation_executed` | Execution result with affected row counts |
| `mutation_failed` | Execution failure details |
| `mutation_expired` | Approval window expired |
| `error` | Any error |
| `done` | End of processing for this message |
| `pong` | Keep-alive response |

### 1.4 Reconnection & Replay

- Server assigns a monotonically increasing **sequence number** to each outbound frame within a session.
- Client can reconnect with `?last_seq=<N>` to replay missed events from an in-memory ring buffer (last 200 events, 5 min TTL).
- If the buffer has been evicted, server sends a `resync_required` frame and the client should reload message history via the existing REST `GET .../messages` endpoint.

### 1.5 Connection Manager

A new `WebSocketConnectionManager` class in `app/core/websocket.py`:
- Maintains `dict[uuid.UUID, WebSocket]` keyed by `session_id`.
- Provides `send_event(session_id, event_type, payload)` for any service to push events.
- Handles graceful shutdown, disconnect cleanup, and heartbeat (`ping`/`pong` every 30s).
- Thread-safe via `asyncio.Lock` per session.

---

## 2. Multi-Table Change-Sets

### 2.1 Change-Set Structure

A single user request (e.g. "add a new department called Engineering and insert 3 employees into it") can produce a **change-set** containing multiple mutations across different tables. The LLM mutation planner outputs a structured proposal:

```json
{
  "change_set_id": "uuid",
  "summary": "Create department 'Engineering' and add 3 employees",
  "expected_total_rows_affected": 4,
  "mutations": [
    {
      "sequence": 1,
      "operation": "insert",
      "table": "departments",
      "columns": ["name", "location"],
      "rows": [
        {"name": "Engineering", "location": "Building A"}
      ],
      "dependencies": []
    },
    {
      "sequence": 2,
      "operation": "insert",
      "table": "employees",
      "columns": ["name", "email", "department_id"],
      "rows": [
        {"name": "Alice", "email": "alice@co.com", "department_id": "$ref:mutations[0].returning.id"},
        {"name": "Bob", "email": "bob@co.com", "department_id": "$ref:mutations[0].returning.id"},
        {"name": "Carol", "email": "carol@co.com", "department_id": "$ref:mutations[0].returning.id"}
      ],
      "dependencies": [0]
    }
  ]
}
```

### 2.2 Row Caps

| Cap | Default | Max | Scope |
|---|---|---|---|
| Per-table row cap (INSERT) | 5 | 50 | Per individual table per change-set |
| Per-table row cap (PATCH) | 1 | 20 | Per individual table per change-set |
| Total change-set row cap | 10 | 100 | Sum of all rows across all tables |
| Tables per change-set | 1 | 5 | Number of distinct tables touched |

- Caps are configurable per-connection by the project owner via the write-policy settings.
- Exceeding any cap is a deterministic rejection before approval is requested.

### 2.3 Cross-Table Dependencies & Ordering

- Mutations within a change-set can declare **dependencies** (by index) to specify execution order.
- A dependent mutation can reference a `$ref:mutations[N].returning.<column>` to use a value returned by a prior INSERT (e.g. auto-generated primary key).
- The executor topologically sorts mutations by dependency and executes them sequentially within a single database transaction.
- Circular dependencies are rejected during validation.

### 2.4 FK-Aware Validation

Before approval, the validator checks:
- INSERT: all FK columns reference existing rows in the target table (verified via SELECT query on the referenced table).
- PATCH: FK columns being updated must also point to valid referenced rows.
- If a `$ref` is used, the FK check is deferred to execution time (after the referenced INSERT completes and returns the actual value).

---

## 3. Connection Write Policy

Extend the `Connection` model with write policy fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `writes_enabled` | `bool` | `false` | Master switch — owner-only toggle |
| `max_insert_rows_per_table` | `int` | `5` | Max rows per INSERT per table in one change-set |
| `max_patch_rows_per_table` | `int` | `1` | Max rows per PATCH per table in one change-set |
| `max_total_rows_per_changeset` | `int` | `10` | Max total rows affected across all tables |
| `max_tables_per_changeset` | `int` | `1` | Max distinct tables in a single change-set |
| `approval_timeout_minutes` | `int` | `15` | Minutes before pending approval expires |
| `undo_window_minutes` | `int` | `0` | Minutes after execution during which soft-undo is available (0 = disabled) |
| `allowed_tables` | `list[str] | null` | `null` | Allowlist of writable tables; null = all tables writable |
| `blocked_tables` | `list[str] | null` | `null` | Denylist of tables that cannot be written; takes precedence over allowlist |

- Only the project owner may enable writes or adjust caps.
- PostgreSQL/MySQL privilege inspection at enable-time: verify the connection role has `INSERT` and `UPDATE` grants; fail closed if unverifiable.
- Documentation requires a least-privilege DB role: only `SELECT`, `INSERT`, `UPDATE` grants; no `DELETE`, DDL, admin, or cross-schema permissions.

---

## 4. Extended Schema Metadata for Safe Writes

Extend the existing `SchemaColumn` model and introspection reflection with additional fields needed for write validation:

| Field | Type | Purpose |
|---|---|---|
| `column_default` | `str | None` | Column default expression (e.g. `nextval(...)`, `now()`) |
| `is_generated` | `bool` | Server-generated or identity column |
| `is_identity` | `bool` | IDENTITY column (PostgreSQL `GENERATED ALWAYS`) |
| `is_autoincrement` | `bool` | Auto-increment (MySQL) / serial (PostgreSQL) |
| `unique_constraints` | (on `SchemaTable`) | List of unique constraint column groups |
| `check_constraints` | (on `SchemaTable`) | List of check constraint expressions |

**Derived metadata (computed, not stored):**
- **Required insert fields**: non-nullable columns without a default, not generated/identity/autoincrement.
- **Patchable columns**: non-generated, non-identity columns; excludes PKs by default.
- **PATCH requires PK**: tables without a primary key cannot be patched (unchanged rule).

---

## 5. Write-Specific Agent Flow

### 5.1 Extended LangGraph Pipeline

Add new nodes and a conditional write path to the existing agent graph:

```text
User message (via WebSocket)
  → intent node [extended: adds "insert" | "patch" | "multi_write" | "unsafe"]
  → [Conditional Router]
     ├── "general" → general_chat → END
     ├── "unsafe"  → unsafe_handler → END
     ├── read intents → sql_generator → sql_executor → ... (existing path, unchanged)
     └── "insert" | "patch" | "multi_write" → mutation_planner
           → missing_field_collector (interactive WebSocket loop)
           → mutation_validator (deterministic safety checks)
           → mutation_previewer (candidate row preview)
           → [wait for approval via WebSocket]
           → mutation_executor (transactional execution)
           → mutation_result_formatter → END
```

### 5.2 New Agent Nodes

1. **`mutation_planner`**: Calls LLM with schema context to produce a typed multi-table change-set proposal. The LLM never generates executable SQL — it outputs a structured JSON plan.

2. **`missing_field_collector`**: Inspects required fields from schema metadata. For each missing required field, sends a `mutation_field_required` WebSocket frame and suspends the graph until the client responds with a `field_response` frame. collect all the required fields in a single socket event or user cancels.

3. **`mutation_validator`**: Deterministic safety checks (detailed in §6).

4. **`mutation_previewer`**: For PATCH operations, executes a `SELECT` using the patch filter to show candidate rows. Sends `mutation_preview` frame with before-state of affected rows.

5. **`mutation_executor`**: Executes the change-set in a single database transaction with row-level locking.

6. **`mutation_result_formatter`**: Formats the outcome into a human-readable NL summary.

### 5.3 Graph State Extension

Extend `AgentState` with:

```python
# --- Write / mutation path ---
mutation_change_set: dict[str, Any] | None    # Structured change-set proposal
mutation_id: UUID | None                       # PendingMutation record ID
mutation_status: str | None                    # Current mutation lifecycle status
mutation_fields_pending: list[str]             # Fields still awaiting user input
mutation_execution_result: dict[str, Any] | None  # Per-table affected counts + returning values
```

---

## 6. Deterministic Safety Rules

Enforced **before** approval is requested — any violation is an immediate rejection:

### 6.1 Global Rules (unchanged + extended)
- No `DELETE`, DDL, grants, transaction commands, multi-statement SQL, or arbitrary SQL execution.
- All values are bound parameters; table/column identifiers come only from cached schema metadata.
- Only `INSERT` and `PATCH` (UPDATE) operations are supported. No `UPSERT`, `MERGE`, or `REPLACE`.

### 6.2 Table-Level Rules
- Table must exist in cached schema metadata.
- Table must not be in `blocked_tables` denylist.
- If `allowed_tables` is set, table must be in the allowlist.
- Column names must exist in cached schema for the target table.
- INSERT: cannot set generated, identity, or autoincrement columns.

### 6.3 Row-Cap Enforcement
- INSERT row count per table ≤ `max_insert_rows_per_table`.
- PATCH row count per table ≤ `max_patch_rows_per_table` (verified by preview SELECT count).
- Total rows across all tables ≤ `max_total_rows_per_changeset`.
- Table count ≤ `max_tables_per_changeset`.

### 6.4 PATCH-Specific Rules (unchanged + extended)
- PATCH always requires a filter condition.
- Preview candidate rows using the table primary key; reject if zero rows match or count exceeds cap.
- At execution, `SELECT ... FOR UPDATE` (PostgreSQL) / `SELECT ... LOCK IN SHARE MODE` (MySQL) the approved primary keys, then update only those keys — prevents approval-to-execution race condition.

### 6.5 FK-Integrity Pre-Checks
- For every FK column value being inserted/updated, verify the referenced row exists (unless using `$ref` deferred references).
- Unique constraint pre-check: for columns covered by a unique constraint, check for existing duplicates before approval.

### 6.6 Type Coercion & Validation
- Coerce user-provided values to the target column's data type before building parameterized SQL.
- Reject values that fail type coercion with a clear error message per field.

---

## 7. HITL Persistence & Approval Flow

### 7.1 `PendingMutation` Model

A new ORM model under the chat domain:

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` PK | |
| `project_id` | `UUID` FK | Multi-tenant scope |
| `session_id` | `UUID` FK | Chat session that initiated the mutation |
| `connection_id` | `UUID` FK | Target database connection |
| `proposer_id` | `UUID` FK | User who triggered the write |
| `approver_id` | `UUID` FK, nullable | User who approved/rejected |
| `status` | `Enum` | See below |
| `change_set_encrypted` | `Text` | Fernet-encrypted JSON of the full change-set |
| `change_set_hash` | `String(64)` | SHA-256 of the plaintext change-set — used for tamper detection |
| `preview_row_counts` | `JSONB` | `{"table_name": count}` per table |
| `total_rows_affected` | `int, nullable` | Filled after execution |
| `execution_result_encrypted` | `Text, nullable` | Encrypted execution details |
| `idempotency_key` | `String(64), nullable, unique` | Client-provided deduplication key |
| `expires_at` | `DateTime` | Approval expiry timestamp |
| `approved_at` | `DateTime, nullable` | |
| `executed_at` | `DateTime, nullable` | |
| `created_at` / `updated_at` | Timestamps | |

**Statuses:** `COLLECTING_INPUT` → `PENDING_APPROVAL` → `APPROVED` | `REJECTED` | `EXPIRED` → `EXECUTING` → `EXECUTED` | `FAILED`

### 7.2 Approval Flow via WebSocket

```text
Server sends: mutation_proposal       → Client sees change-set preview
Server sends: mutation_approval_required → Client shows Approve/Reject controls
Client sends: { type: "approve", mutation_id, idempotency_key }
Server:
  1. Verify sender is project owner
  2. Verify mutation status == PENDING_APPROVAL
  3. Verify not expired
  4. Verify change_set_hash matches stored hash (tamper detection)
  5. Transition to APPROVED → EXECUTING
  6. Execute in transaction
  7. Send mutation_executed or mutation_failed
```

### 7.3 REST Fallback Endpoints

For clients that cannot use WebSocket or for programmatic approval:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `.../mutations/{mutation_id}/approve` | Approve a pending mutation |
| `POST` | `.../mutations/{mutation_id}/reject` | Reject a pending mutation |
| `GET` | `.../mutations/{mutation_id}` | Get mutation status + preview |
| `GET` | `.../mutations` | List mutations for session (paginated) |
| `POST` | `.../mutations/{mutation_id}/undo` | Soft-undo within undo window |

All use the standard `ApiResponse` envelope. Owner-only access enforced.

### 7.4 Approval Expiry

- Default 15 minutes (configurable per connection).
- A background task (or lazy check on access) transitions `PENDING_APPROVAL` mutations past `expires_at` to `EXPIRED`.
- Expired mutations send a `mutation_expired` WebSocket frame if the connection is still open.

---

## 8. Transactional Execution Engine

### 8.1 Execution Strategy

```text
BEGIN TRANSACTION
  for each mutation in topological order:
    if INSERT:
      INSERT INTO <table> (<cols>) VALUES (<params>) RETURNING <pk_cols>
      store returning values for $ref resolution
    if PATCH:
      SELECT <pk_cols> FROM <table> WHERE <filter> FOR UPDATE  -- row lock
      verify locked row count == approved preview count
      if mismatch → ROLLBACK, status = FAILED, reason = "row count changed"
      UPDATE <table> SET <cols> = <params> WHERE <pk> IN (<locked_pks>)
COMMIT
```

- Single transaction across all mutations in the change-set — all succeed or all roll back.
- `RETURNING` clause (PostgreSQL) / `LAST_INSERT_ID()` (MySQL) used to resolve `$ref` dependencies.
- Connection acquired from the existing `ConnectionManager` using the target database engine.

### 8.2 Before/After Snapshots

- For PATCH operations, capture the pre-update state of affected rows (from the `FOR UPDATE` select).
- Store encrypted in the audit record for compliance and potential undo.
- Sensitive column values (if marked in semantic layer annotations) are redacted in API responses but retained encrypted in audit.

---

## 9. Soft-Undo Window

### 9.1 Concept

If `undo_window_minutes > 0` on the connection write policy, an executed change-set can be **soft-undone** within the configured window:

- **INSERT undo**: `DELETE FROM <table> WHERE <pk> IN (<inserted_pks>)`.
- **PATCH undo**: `UPDATE <table> SET <cols> = <before_values> WHERE <pk> IN (<patched_pks>)`.

### 9.2 Constraints

- Undo is best-effort: if referential integrity prevents deletion (e.g. inserted row is now referenced by another table), undo fails gracefully with a clear error.
- Undo creates its own audit record with `operation = "undo"`.
- Undo is a **separate approval flow** — it requires owner approval just like the original mutation.
- After the undo window expires, the mutation is considered permanent.

---

## 10. Rate Limiting & Abuse Prevention

| Control | Value | Scope |
|---|---|---|
| Max pending mutations per session | 3 | Prevents spamming approval queue |
| Max mutations per project per hour | 30 | Prevents runaway automation |
| Max total rows written per project per hour | 200 | Hard safety limit |
| Cooldown after failed execution | 60 seconds | Per session |

- Enforced in the mutation planner node before constructing the proposal.
- Rate limit state stored in Redis (if available) or in-memory with TTL.

---

## 11. Dry-Run Mode

- A `dry_run: bool` flag on the `message` WebSocket frame (or query parameter on REST).
- When enabled, the full pipeline runs — intent classification, mutation planning, validation, preview — but stops before requesting approval.
- Returns the complete change-set proposal and preview without persisting a `PendingMutation` record.
- Useful for testing write configurations and validating LLM output without risk.

---

## 12. Conflict Detection

Before executing, the mutation executor performs **optimistic concurrency checks**:

- **PATCH**: compare the `updated_at` timestamp (if the table has one) of each target row against the value seen during preview. If any row was modified between preview and execution, abort with `CONFLICT` status.
- **INSERT with unique constraints**: re-check unique constraint columns immediately before insert within the transaction. If a conflicting row now exists, abort with `CONFLICT`.
- On conflict, the mutation transitions to `FAILED` with a clear `conflict_details` field explaining which rows/constraints conflicted.

---

## 13. Append-Only Audit Records

### 13.1 `MutationAuditLog` Model

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` PK | |
| `project_id` | `UUID` FK | |
| `connection_id` | `UUID` FK | |
| `mutation_id` | `UUID` FK | Reference to `PendingMutation` |
| `initiator_id` | `UUID` FK | User who triggered |
| `approver_id` | `UUID` FK, nullable | User who approved |
| `operation` | `String` | `insert` / `patch` / `undo` |
| `tables_affected` | `JSONB` | `[{"table": "...", "operation": "insert", "row_count": N}]` |
| `total_rows_affected` | `int` | |
| `change_set_hash` | `String(64)` | SHA-256 for integrity verification |
| `before_snapshot_encrypted` | `Text, nullable` | Encrypted pre-update state (PATCH only) |
| `after_snapshot_encrypted` | `Text, nullable` | Encrypted post-update state |
| `status` | `String` | `executed` / `failed` / `undone` |
| `error_details` | `Text, nullable` | Failure reason if applicable |
| `latency_ms` | `int` | Execution duration |
| `created_at` | `DateTime` | Immutable |

- All value data is Fernet-encrypted at rest.
- Never log plaintext target values or credentials.
- Audit records are append-only — no UPDATE or DELETE operations on this table.

---

## 14. Implementation Order

1. **WebSocket infrastructure** (`app/core/websocket.py`): `WebSocketConnectionManager`, wire protocol, auth handshake, heartbeat, reconnection buffer.
2. **WebSocket chat endpoint** (`chat/router.py`): New `ws` route, integrate with existing `ChatService`, deprecate SSE endpoint.
3. **Connection write policy**: Schema migration adding write policy columns to `connections` table. Update `Connection` model, schemas, and service.
4. **Extended schema introspection**: Add `column_default`, `is_generated`, `is_identity`, `is_autoincrement` to `SchemaColumn`. Add `unique_constraints`, `check_constraints` to `SchemaTable`. Update reflection logic.
5. **`PendingMutation` and `MutationAuditLog`**: Schema migrations and ORM models under the chat domain.
6. **Mutation planner node**: LLM-powered structured change-set generation with multi-table support.
7. **Missing-field collector node**: Interactive WebSocket prompt/response loop.
8. **Mutation validator**: Deterministic safety checks, FK validation, type coercion, cap enforcement.
9. **Mutation previewer**: Row-level preview with before-state capture.
10. **Mutation executor**: Transactional execution with row locking, `$ref` resolution, and conflict detection.
11. **Approval flow**: WebSocket approve/reject handling + REST fallback endpoints.
12. **Audit logging**: Encrypted append-only audit records.
13. **Rate limiting**: Per-session and per-project mutation rate limits.
14. **Dry-run mode**: Flag support in WebSocket frame and REST.
15. **Soft-undo**: Undo window, undo execution, undo approval flow.
16. **Privilege verification**: Dialect-aware PostgreSQL/MySQL privilege inspection at write-enable time.
17. **Frontend**: WebSocket client, approval UI, change-set preview, undo controls.

---

## 15. File Changes Summary

### Core Infrastructure
- **[NEW]** `backend/app/core/websocket.py` — `WebSocketConnectionManager`, frame serialization, auth, heartbeat, reconnection buffer.

### Chat Domain
- **[MODIFY]** `backend/app/domain/chat/router.py` — Add WebSocket endpoint, deprecate SSE endpoint.
- **[MODIFY]** `backend/app/domain/chat/services.py` — Refactor `send_message_stream` to emit events via `WebSocketConnectionManager`. Add mutation orchestration methods.
- **[MODIFY]** `backend/app/domain/chat/models.py` — Add `PendingMutation` and `MutationAuditLog` ORM models.
- **[MODIFY]** `backend/app/domain/chat/schemas.py` — Add mutation-related Pydantic schemas (change-set, approval, preview, audit).
- **[MODIFY]** `backend/app/domain/chat/repository.py` — Add `PendingMutationRepository` and `MutationAuditRepository`.

### Agent Domain
- **[MODIFY]** `backend/app/domain/agent/state.py` — Extend `AgentState` with mutation fields.
- **[MODIFY]** `backend/app/domain/agent/graph.py` — Add write-path nodes and conditional routing.
- **[MODIFY]** `backend/app/domain/agent/guardrail.py` — Differentiate allowed write intents from unsafe intents when writes are enabled.
- **[MODIFY]** `backend/app/domain/agent/sql_validator.py` — Add `validate_write_sql()` for parameterized INSERT/UPDATE validation.
- **[NEW]** `backend/app/domain/agent/nodes/mutation_planner.py` — LLM-powered change-set generation.
- **[NEW]** `backend/app/domain/agent/nodes/missing_field_collector.py` — Interactive field collection via WebSocket.
- **[NEW]** `backend/app/domain/agent/nodes/mutation_validator.py` — Deterministic safety checks + FK validation.
- **[NEW]** `backend/app/domain/agent/nodes/mutation_previewer.py` — Candidate row preview.
- **[NEW]** `backend/app/domain/agent/nodes/mutation_executor.py` — Transactional execution engine.
- **[NEW]** `backend/app/domain/agent/nodes/mutation_result_formatter.py` — NL summary for write results.

### Connections Domain
- **[MODIFY]** `backend/app/domain/connections/models.py` — Add write policy columns.
- **[MODIFY]** `backend/app/domain/connections/schemas.py` — Add write policy schemas.
- **[MODIFY]** `backend/app/domain/connections/services.py` — Add privilege verification and write policy management.

### Schema Introspection Domain
- **[MODIFY]** `backend/app/domain/schema_introspection/models.py` — Add `column_default`, `is_generated`, `is_identity`, `is_autoincrement` to `SchemaColumn`. Add constraint fields to `SchemaTable`.
- **[MODIFY]** `backend/app/domain/schema_introspection/services.py` — Extend reflection to capture defaults, generated columns, unique/check constraints.

### Migrations
- **[NEW]** `backend/alembic/versions/xxx_add_connection_write_policy.py`
- **[NEW]** `backend/alembic/versions/xxx_extend_schema_column_metadata.py`
- **[NEW]** `backend/alembic/versions/xxx_add_pending_mutations_and_audit.py`

---

## 16. Test Plan

### Unit Tests
- INSERT asks for every required field and never executes before owner approval.
- PATCH without a filter is rejected.
- PATCH with zero rows or over the configured cap is rejected.
- Multi-table change-set with 3 tables and 15 total rows is accepted when caps allow, rejected when they don't.
- `$ref` resolution correctly chains INSERT returning values into dependent mutations.
- Circular dependency in change-set is rejected.
- FK validation catches invalid references before approval.
- Type coercion rejects incompatible values with clear error messages.
- A PATCH approved for one row cannot update additional rows if matching rows change before execution.
- Non-owner approval returns `403`; expired, rejected, altered, and duplicate approvals cannot cause duplicate writes.
- Idempotency key replay returns stored outcome without re-execution.
- PostgreSQL and MySQL privilege checks fail closed when write capability is unavailable or unverifiable.
- Parameter binding blocks SQL injection through values, filters, and chat input.
- Read-only queries retain the existing validator and execution behavior.
- Table allowlist/denylist enforcement works correctly.
- Rate limiting rejects mutations when limits are exceeded.
- Dry-run mode completes the full pipeline without persisting or executing.
- Conflict detection aborts when rows change between preview and execution.
- Soft-undo correctly reverses INSERT (delete) and PATCH (restore before-state).
- Undo fails gracefully when referential integrity prevents reversal.

### WebSocket Tests
- WebSocket handshake with valid JWT succeeds; invalid JWT returns `4001` close code.
- Client can send `message`, receive streaming events, and the full read flow works over WebSocket.
- Interactive field collection: server sends `mutation_field_required`, client responds with `field_response`, loop completes.
- Approval via WebSocket: client sends `approve`, server executes and sends `mutation_executed`.
- Reconnection with `?last_seq=N` replays missed events correctly.
- Heartbeat `ping`/`pong` keeps connection alive.

### Integration Tests
- End-to-end: user sends "add a customer named John" via WebSocket → field collection → preview → approve → executed → audit record created.
- End-to-end multi-table: user sends "add department and 3 employees" → change-set with `$ref` → approve → both tables populated in one transaction.
- Verify `ruff check .`, `pyright`, and `pytest` all pass.

---

## 17. Assumptions

- Write support is limited to PostgreSQL and MySQL; all other dialects remain read-only.
- Existing connections are upgraded through an owner-controlled write-enable setting.
- Only the project owner may approve writes (and undo).
- The existing read-only SQL path and SSE streaming remain functional (SSE deprecated but not removed).
- The WebSocket endpoint coexists with existing REST endpoints — it does not replace session CRUD or message history APIs.
- Rate limit storage uses in-memory state initially; Redis integration is optional and can be added later.
- Soft-undo is best-effort and not guaranteed to succeed if the database state has changed.
- The LLM mutation planner is constrained to produce structured JSON proposals — it never generates executable SQL directly.
