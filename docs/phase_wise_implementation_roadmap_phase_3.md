# Phased Implementation Roadmap: Safe INSERT/PATCH with HITL via WebSocket

This document outlines the step-by-step implementation phases for executing the design specified in [implementation_plan_phase_3_write_operations_hitl.md](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/docs/implementation_plan_phase_3_write_operations_hitl.md).

---

## Phase Overview & Dependency Graph

```text
[Phase 1: WebSocket Infrastructure & Streaming Baseline]
       │
       ▼
[Phase 2: Database Models, Write Policies & Schema Introspection Extensions]
       │
       ▼
[Phase 3: Write Guardrails, Validation Engine & Cap Enforcement]
       │
       ▼
[Phase 4: Agent Write Path & LLM Mutation Planning (LangGraph)]
       │
       ▼
[Phase 5: Interactive HITL Collection & WebSocket Approval Protocol]
       │
       ▼
[Phase 6: Transactional Execution Engine, Snapshots & Append-Only Auditing]
       │
       ▼
[Phase 7: Advanced Safeguards (Soft-Undo, Concurrency Conflicts, Rate Limiting, Dry-Run)]
       │
       ▼
[Phase 8: Frontend UI/UX, End-to-End Testing & Verification]
```

---

## Phase 1: WebSocket Transport Infrastructure & Streaming Baseline
> **Goal:** Establish a robust bidirectional WebSocket communication layer for chat sessions to stream read executions, laying the groundwork for interactive HITL frames without breaking existing SSE behavior.

### 1.1 Scope & Tasks
1. **WebSocket Connection Manager (`backend/app/core/websocket.py`)**:
   - Create `WebSocketConnectionManager` managing active connections by `session_id`.
   - Implement connection lifecycle: JWT auth via query param (`?token=...`), rejection codes (e.g. `4001` on invalid/expired auth), heartbeat/ping-pong handling.
   - Implement monotonic sequence numbering per outbound frame and in-memory ring buffer (replay up to 200 events on reconnect via `?last_seq=N`).
2. **WebSocket Router Integration (`backend/app/domain/chat/router.py`)**:
   - Add route `/{project_id}/chat/sessions/{session_id}/ws`.
   - Maintain the existing SSE endpoint `POST /{project_id}/chat/sessions/{session_id}/messages` as a deprecated fallback.
3. **Chat Service Streaming Refactor (`backend/app/domain/chat/services.py`)**:
   - Decouple agent graph streaming from HTTP SSE text formatting. Provide a unified generator/emitter that can output to both WebSocket and SSE.
4. **Verification**:
   - Unit tests testing WebSocket handshake, valid/invalid JWTs, client message frames, and event broadcasting.

---

## Phase 2: Database Models, Write Policies & Extended Schema Metadata
> **Goal:** Lay the database persistence foundations for connection write permissions, row-cap limits, mutation lifecycles, audit logging, and extended schema introspection.

### 2.1 Scope & Tasks
1. **Connection Write Policy (`backend/app/domain/connections/models.py`, `schemas.py`)**:
   - Add fields: `writes_enabled`, `max_insert_rows_per_table`, `max_patch_rows_per_table`, `max_total_rows_per_changeset`, `max_tables_per_changeset`, `approval_timeout_minutes`, `undo_window_minutes`, `allowed_tables`, `blocked_tables`.
   - Update connection Pydantic schemas and add owner-only endpoint/service logic for updating write policies.
2. **Extended Schema Metadata (`backend/app/domain/schema_introspection/models.py`, `services.py`)**:
   - In `SchemaColumn`: add `column_default`, `is_generated`, `is_identity`, `is_autoincrement`.
   - In `SchemaTable`: add structure/columns for unique and check constraints.
   - Update reflection logic in `SchemaIntrospectionService` (both PostgreSQL & MySQL dialect inspectors).
3. **Pending Mutation & Audit Log Models (`backend/app/domain/chat/models.py`, `repository.py`)**:
   - Add `PendingMutation` model (encrypted payload, hash, status, row preview counts, expiry, idempotency key).
   - Add `MutationAuditLog` model (append-only, before/after encrypted snapshots, affected counts, hash, status).
   - Create corresponding repository classes subclassing `CRUDBase`.
4. **Alembic Migrations**:
   - Generate and test migration scripts for `connections`, `schema_*`, and `chat` additions.

---

## Phase 3: Write Guardrails, Validation Engine & Cap Enforcement
> **Goal:** Create deterministic pre-execution validation checks that run before approval is ever requested.

### 3.1 Scope & Tasks
1. **Guardrail Intent Separation (`backend/app/domain/agent/guardrail.py`)**:
   - Update regex/fast-path checks: when `writes_enabled` is true, allow structured INSERT/PATCH while still strictly blocking destructive DDL (`DROP`, `TRUNCATE`, `DELETE`, `ALTER`, `GRANT`, `REVOKE`).
2. **Deterministic Mutation Validator (`backend/app/domain/agent/nodes/mutation_validator.py`)**:
   - Table existence check against cached schema.
   - Table allowlist/denylist verification.
   - Column existence and writeability check (reject writes to generated/identity/autoincrement columns).
   - Enforce primary key existence for PATCH target tables.
   - Enforce mandatory WHERE/filter clause on all PATCH operations.
   - Validate row caps: per-table INSERT cap, per-table PATCH cap, total change-set cap, and table count cap.
3. **FK & Type Validation**:
   - Foreign key validation: query referenced tables to ensure target records exist (or defer for `$ref`).
   - Strict parameter type coercion and validation matching schema column definitions.

---

## Phase 4: Agent Write Path & LLM Mutation Planning
> **Goal:** Update the LangGraph agent to classify write intent, retrieve writable schema metadata, and construct structured multi-table change-sets.

### 4.1 Scope & Tasks
1. **Agent State Extension (`backend/app/domain/agent/state.py`)**:
   - Add `mutation_change_set`, `mutation_id`, `mutation_status`, `mutation_fields_pending`, `mutation_execution_result`.
2. **Intent Node Updates (`backend/app/domain/agent/nodes/intent.py`)**:
   - Classify intents into `lookup`, `aggregation`, `comparison`, `trend`, `general`, `unsafe`, and new write intents: `insert`, `patch`, `multi_write`.
3. **Mutation Planner Node (`backend/app/domain/agent/nodes/mutation_planner.py`)**:
   - Prompt engineering to instruct the LLM to output typed, structured JSON mutation proposals (operations, tables, columns, values/filters, cross-table `$ref` links). The LLM is strictly prohibited from generating raw executable DML SQL.
4. **Graph Routing (`backend/app/domain/agent/graph.py`)**:
   - Wire conditional branches after intent classification to divert write intents to `mutation_planner`.

---

## Phase 5: Interactive HITL Collection & WebSocket Approval Protocol
> **Goal:** Implement the bidirectional WebSocket flow to collect missing fields, render change-set previews, and require project-owner approval.

### 5.1 Scope & Tasks
1. **Missing Field Collector (`backend/app/domain/agent/nodes/missing_field_collector.py`)**:
   - Inspect required columns (non-nullable columns without defaults).
   - When required fields are omitted: emit `mutation_field_required` frame via WebSocket.
   - Suspend graph/session until `field_response` frame is received from client, then resume validation.
2. **Mutation Previewer Node (`backend/app/domain/agent/nodes/mutation_previewer.py`)**:
   - Execute safe `SELECT` queries for PATCH operations to fetch candidate matching rows using primary keys.
   - Emit `mutation_preview` and `mutation_approval_required` frames containing row previews, affected counts, and configured caps.
3. **Approval Handlers (`chat/services.py`, `chat/router.py`)**:
   - Handle client WebSocket `approve` and `reject` frames.
   - Expose REST fallback endpoints: `POST .../mutations/{mutation_id}/approve` and `.../reject`.
   - Security checks: verify current user is the **project owner**, check proposal expiration (`15 min` default), verify change-set SHA-256 hash against stored hash.

---

## Phase 6: Transactional Execution Engine & Auditing
> **Goal:** Implement safe, atomic, multi-table parameterized execution with row locking and append-only audit logging.

### 6.1 Scope & Tasks
1. **Mutation Executor (`backend/app/domain/agent/nodes/mutation_executor.py`)**:
   - Dependency ordering: topologically sort mutations in a change-set.
   - Resolve `$ref` dynamic dependencies (e.g. resolve inserted parent ID to child FK).
   - Execute within a single target database transaction (`BEGIN ... COMMIT / ROLLBACK`).
   - Dialect-specific row locking for PATCH: `SELECT ... FOR UPDATE` (PostgreSQL) / `SELECT ... LOCK IN SHARE MODE` (MySQL).
   - Verify locked row count exactly matches the previewed count; abort transaction if count differs.
   - Execute parameterized `INSERT` and `UPDATE` statements using only allowlisted schema identifiers.
2. **Audit Logging Service (`chat/services.py`, `chat/repository.py`)**:
   - Encrypt before/after row states and change-set values using platform Fernet encryption.
   - Write immutable records into `mutation_audit_logs`.
3. **Result Formatter**:
   - Emit `mutation_executed` (or `mutation_failed`) WebSocket frame with affected counts and human-readable confirmation.

---

## Phase 7: Advanced Safeguards (Soft-Undo, Concurrency, Rate Limiting & Dry-Run)
> **Goal:** Layer production-grade safeguards onto the write pipeline.

### 7.1 Scope & Tasks
1. **Dry-Run Mode**:
   - Support `dry_run: true` in WebSocket/REST message payload. Run full planning, validation, and preview without creating pending mutations or executing writes.
2. **Concurrency Conflict Detection**:
   - Compare `updated_at` / version timestamps on previewed rows before committing PATCH updates.
   - Abort on race conditions with `CONFLICT` status and actionable details.
3. **Rate Limiting & Cooldowns**:
   - Enforce limits: max 3 pending mutations per session, 30 writes/project/hour, 200 total rows/project/hour, 60s cooldown on failure.
4. **Soft-Undo Engine**:
   - If `undo_window_minutes > 0`, allow owner to call `POST .../mutations/{id}/undo`.
   - Best-effort reversal: delete inserted rows, restore patched rows to pre-update snapshot; log dedicated undo audit record.

---

## Phase 8: Frontend UI/UX, End-to-End Verification & Documentation
> **Goal:** Provide seamless user-facing controls and verify the full system under test suites and dialect edge cases.

### 8.1 Scope & Tasks
1. **Frontend Chat & HITL Interface**:
   - Connect chat surface to WebSocket endpoint with auto-reconnect and sequence replay.
   - Render inline interactive cards: missing field inputs, multi-table change-set diff previews, Approve/Reject buttons, and Undo actions.
2. **Comprehensive Test Suite**:
   - Unit tests: validation rules, cap enforcement, circular dependency detection, type coercion.
   - WebSocket integration tests: full interaction loop (query → prompt for field → reply → preview → approve → executed).
   - Multi-table transactional tests: verify rollbacks on partial failure, verify `$ref` resolution.
3. **Code Quality & Verification**:
   - Run `ruff check .`, `pyright`, and `pytest`.
