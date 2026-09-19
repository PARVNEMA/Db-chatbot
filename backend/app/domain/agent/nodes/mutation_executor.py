"""Agent domain — Transactional Mutation Executor Node (Phase 6).

Executes approved multi-table change-sets within a single atomic database transaction.
Responsibilities:
1. Topologically sorts mutations in a change-set by dependency order (detecting cycles).
2. Dynamically resolves cross-table $ref references using RETURNING (PostgreSQL/SQLite) or LAST_INSERT_ID() (MySQL).
3. Enforces optimistic concurrency row locking (SELECT ... FOR UPDATE) for PATCH mutations.
4. Captures and Fernet-encrypts pre- and post-update row snapshots.
5. Emits real-time execution events over WebSocket.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.security import encrypt_secret
from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.state import AgentState
from app.domain.connections.manager import serialize_row_value

logger = logging.getLogger(__name__)

# Regex pattern for resolving cross-mutation dynamic references:
# e.g. "$ref:mutations[0].returning.id" or "$ref:mutations[1].returning.dept_id"
REF_PATTERN = re.compile(r"^\$ref:mutations\[(\d+)\]\.returning\.([a-zA-Z0-9_]+)$")


class ConcurrencyConflictError(RuntimeError):
    """Raised when the locked row count for a PATCH operation differs from preview."""


@dataclass
class ExecutionResult:
    """Outcome of an atomic change-set execution."""

    success: bool
    total_rows_affected: int
    tables_affected: list[dict[str, Any]] = field(default_factory=list)
    before_snapshots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    after_snapshots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    before_snapshot_encrypted: str | None = None
    after_snapshot_encrypted: str | None = None
    returning_registry: dict[Any, dict[str, Any]] = field(default_factory=dict)
    latency_ms: int = 0
    error_message: str | None = None


def topological_sort_mutations(
    mutations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort mutations in topological dependency order using Kahn's algorithm.

    Resolves both explicit `dependencies` list (which can contain sequence numbers
    or 0-based indices) and implicit references embedded in row values.

    Raises:
        ValueError: If a circular dependency is detected.
    """
    if len(mutations) <= 1:
        return list(mutations)

    n = len(mutations)
    # Map sequence -> index and index -> mutation
    seq_to_idx: dict[int, int] = {}
    for idx, m in enumerate(mutations):
        seq = m.get("sequence", idx)
        seq_to_idx[seq] = idx

    adj: dict[int, list[int]] = defaultdict(list)
    in_degree: dict[int, int] = dict.fromkeys(range(n), 0)

    for idx, m in enumerate(mutations):
        deps = list(m.get("dependencies", []))

        # Also scan row values for implicit $ref:mutations[N].returning.<col>
        for row in m.get("rows", []):
            if isinstance(row, dict):
                for val in row.values():
                    if isinstance(val, str):
                        match = REF_PATTERN.match(val.strip())
                        if match:
                            ref_target = int(match.group(1))
                            if ref_target not in deps:
                                deps.append(ref_target)

        # Normalize deps to 0-based indices
        normalized_deps: set[int] = set()
        for dep in deps:
            if dep in seq_to_idx:
                normalized_deps.add(seq_to_idx[dep])
            elif 0 <= dep < n:
                normalized_deps.add(dep)

        for parent_idx in normalized_deps:
            if parent_idx != idx:
                adj[parent_idx].append(idx)
                in_degree[idx] += 1

    # Kahn's algorithm
    queue = deque([i for i in range(n) if in_degree[i] == 0])
    sorted_indices: list[int] = []

    while queue:
        u = queue.popleft()
        sorted_indices.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(sorted_indices) != n:
        raise ValueError("Circular dependency detected in change-set mutations.")

    return [mutations[i] for i in sorted_indices]


def resolve_ref_value(
    val: Any,
    returning_registry: dict[Any, dict[str, Any]],
) -> Any:
    """Recursively resolve dynamic $ref strings against returning registry."""
    if isinstance(val, str):
        match = REF_PATTERN.match(val.strip())
        if match:
            target_key = int(match.group(1))
            col_name = match.group(2)
            reg = returning_registry.get(target_key)
            if reg is None or col_name not in reg:
                raise ValueError(
                    f"Unable to resolve dynamic reference '{val}': parent mutation {target_key} "
                    f"did not return column '{col_name}'. Available: {list(reg.keys()) if reg else 'None'}"
                )
            return reg[col_name]
        return val

    if isinstance(val, dict):
        return {k: resolve_ref_value(v, returning_registry) for k, v in val.items()}

    if isinstance(val, list):
        return [resolve_ref_value(elem, returning_registry) for elem in val]

    return val


def resolve_mutation_refs(
    mutation: dict[str, Any],
    returning_registry: dict[Any, dict[str, Any]],
) -> dict[str, Any]:
    """Return a deep copy of the mutation with all $ref values resolved."""
    resolved = dict(mutation)
    if "rows" in resolved and isinstance(resolved["rows"], list):
        resolved["rows"] = [
            resolve_ref_value(row, returning_registry) for row in resolved["rows"]
        ]
    if "filter" in resolved and isinstance(resolved["filter"], dict):
        resolved["filter"] = resolve_ref_value(resolved["filter"], returning_registry)
    return resolved


async def _execute_insert(
    conn: AsyncConnection,
    mutation: dict[str, Any],
    dialect: str,
    returning_registry: dict[Any, dict[str, Any]],
    mutation_idx: int,
    mutation_seq: int,
) -> int:
    """Execute parameterized INSERT and collect returning values."""
    table = mutation["table"]
    rows = mutation.get("rows", [])
    if not rows:
        return 0

    dialect_lower = dialect.lower()
    rows_affected = 0

    for _r_idx, row in enumerate(rows):
        cols = list(row.keys())
        param_names = [f"val_{i}" for i in range(len(cols))]
        col_list_str = ", ".join(f'"{c}"' if dialect_lower != "mysql" else f"`{c}`" for c in cols)
        val_placeholders_str = ", ".join(f":{p}" for p in param_names)
        params = {param_names[i]: row[cols[i]] for i in range(len(cols))}

        # Concurrency check: if row provides an explicit primary key, ensure no conflict
        if "id" in row and row["id"] is not None:
            id_quoted = '"id"' if dialect_lower != "mysql" else "`id`"
            check_sql = f"SELECT 1 FROM {table} WHERE {id_quoted} = :check_id"
            try:
                chk_res = await conn.execute(text(check_sql), {"check_id": row["id"]})
                if chk_res.first() is not None:
                    raise ConcurrencyConflictError(
                        f"Concurrency conflict on table '{table}': a conflicting row with id={row['id']} already exists."
                    )
            except ConcurrencyConflictError:
                raise
            except Exception:
                pass  # If table doesn't have an 'id' column, continue normally

        # Construct RETURNING clause based on dialect
        if "postgres" in dialect_lower or "sqlite" in dialect_lower:
            sql = f"INSERT INTO {table} ({col_list_str}) VALUES ({val_placeholders_str}) RETURNING *"
            result = await conn.execute(text(sql), params)
            returned_mapping = result.mappings().first()
            if returned_mapping:
                ret_dict = {k: serialize_row_value(v) for k, v in returned_mapping.items()}
                returning_registry[mutation_seq] = ret_dict
                if mutation_idx not in returning_registry:
                    returning_registry[mutation_idx] = ret_dict
            rows_affected += 1

        elif "mysql" in dialect_lower or "mariadb" in dialect_lower:
            sql = f"INSERT INTO `{table}` ({col_list_str}) VALUES ({val_placeholders_str})"
            await conn.execute(text(sql), params)
            last_id_res = await conn.execute(text("SELECT LAST_INSERT_ID() AS id"))
            last_id_mapping = last_id_res.mappings().first()
            ret_dict = dict(row)
            if last_id_mapping and last_id_mapping.get("id") is not None:
                ret_dict["id"] = serialize_row_value(last_id_mapping["id"])
            returning_registry[mutation_seq] = ret_dict
            if mutation_idx not in returning_registry:
                returning_registry[mutation_idx] = ret_dict
            rows_affected += 1

        else:
            # Generic fallback
            sql = f"INSERT INTO {table} ({col_list_str}) VALUES ({val_placeholders_str})"
            await conn.execute(text(sql), params)
            returning_registry[mutation_seq] = dict(row)
            if mutation_idx not in returning_registry:
                returning_registry[mutation_idx] = dict(row)
            rows_affected += 1

    return rows_affected


async def _execute_patch(
    conn: AsyncConnection,
    mutation: dict[str, Any],
    dialect: str,
    preview_row_counts: dict[str, int] | None,
    before_snapshots: dict[str, list[dict[str, Any]]],
    after_snapshots: dict[str, list[dict[str, Any]]],
    candidate_rows: list[dict[str, Any]] | None = None,
) -> int:
    """Execute dialect-specific row-locking, concurrency check, and UPDATE."""
    table = mutation["table"]
    patch_filter = mutation.get("filter") or {}
    rows = mutation.get("rows", [])
    dialect_lower = dialect.lower()

    if not patch_filter:
        raise ValueError(f"PATCH operation on table '{table}' requires a non-empty filter.")

    # 1. Build parameterized WHERE clause for locking query
    where_parts: list[str] = []
    filter_params: dict[str, Any] = {}
    for i, (col, val) in enumerate(patch_filter.items()):
        p_name = f"f_{i}"
        col_quoted = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
        where_parts.append(f"{col_quoted} = :{p_name}")
        filter_params[p_name] = val

    where_sql = " AND ".join(where_parts)

    # 2. Select with row locking (PostgreSQL/MySQL)
    if "postgres" in dialect_lower or "mysql" in dialect_lower or "mariadb" in dialect_lower:
        lock_sql = f"SELECT * FROM {table} WHERE {where_sql} FOR UPDATE"
    else:
        # SQLite transaction is serialized at DB file level
        lock_sql = f"SELECT * FROM {table} WHERE {where_sql}"

    lock_result = await conn.execute(text(lock_sql), filter_params)
    locked_rows = [
        {k: serialize_row_value(v) for k, v in row.items()}
        for row in lock_result.mappings().all()
    ]

    # 3. Concurrency Check: verify locked count matches approved preview count
    expected_count = 1
    if preview_row_counts and table in preview_row_counts:
        expected_count = preview_row_counts[table]
    elif rows:
        expected_count = len(rows)

    if len(locked_rows) != expected_count or len(locked_rows) == 0:
        raise ConcurrencyConflictError(
            f"Concurrency conflict on table '{table}': locked {len(locked_rows)} row(s), "
            f"but approved preview expected {expected_count}. "
            "Underlying data was modified concurrently. Aborting transaction."
        )

    # 3.1 Version / Timestamp concurrency check (Phase 7)
    if candidate_rows:
        cand_map = {r.get("id"): r for r in candidate_rows if r.get("id") is not None}
        for lr in locked_rows:
            lr_id = lr.get("id")
            if lr_id is not None and lr_id in cand_map:
                cand = cand_map[lr_id]
                for ts_col in ("updated_at", "last_modified", "modified_at", "version"):
                    if ts_col in cand and ts_col in lr and cand[ts_col] is not None and lr[ts_col] is not None:
                        if str(cand[ts_col]) != str(lr[ts_col]):
                            raise ConcurrencyConflictError(
                                f"Concurrency conflict on table '{table}': row id={lr_id} was modified concurrently "
                                f"(preview {ts_col}='{cand[ts_col]}' != current {ts_col}='{lr[ts_col]}'). "
                                "Aborting transaction."
                            )

    # Capture before snapshot
    before_snapshots.setdefault(table, []).extend(locked_rows)

    # 4. Perform parameterized UPDATE
    # If multiple updates in rows, apply them; default is first row dict
    update_data = rows[0] if rows else {}
    if not update_data:
        raise ValueError(f"PATCH operation on table '{table}' has no columns to update in rows.")

    set_parts: list[str] = []
    update_params = dict(filter_params)
    for i, (col, val) in enumerate(update_data.items()):
        u_name = f"u_{i}"
        col_quoted = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
        set_parts.append(f"{col_quoted} = :{u_name}")
        update_params[u_name] = val

    set_sql = ", ".join(set_parts)
    update_stmt = f"UPDATE {table} SET {set_sql} WHERE {where_sql}"
    await conn.execute(text(update_stmt), update_params)

    # 5. Capture after snapshot
    after_select_sql = f"SELECT * FROM {table} WHERE {where_sql}"
    after_result = await conn.execute(text(after_select_sql), filter_params)
    after_rows = [
        {k: serialize_row_value(v) for k, v in row.items()}
        for row in after_result.mappings().all()
    ]
    after_snapshots.setdefault(table, []).extend(after_rows)

    return len(locked_rows)


async def execute_change_set(
    engine: AsyncEngine,
    dialect: str,
    change_set: dict[str, Any],
    preview_row_counts: dict[str, int] | None = None,
    candidate_rows: dict[str, list[dict[str, Any]]] | None = None,
) -> ExecutionResult:
    """Execute an entire multi-table change-set within a single atomic transaction.

    Rolls back automatically on any error, returning an ExecutionResult with
    failure metadata and clean before/after snapshots.
    """
    start_time = time.perf_counter()
    raw_mutations = change_set.get("mutations", [])

    if not raw_mutations:
        return ExecutionResult(
            success=True,
            total_rows_affected=0,
            latency_ms=0,
        )

    # 1. Topologically sort mutations by dependencies
    try:
        ordered_mutations = topological_sort_mutations(raw_mutations)
    except Exception as sort_err:
        logger.error("Topological sort failed: %s", sort_err)
        return ExecutionResult(
            success=False,
            total_rows_affected=0,
            error_message=str(sort_err),
            latency_ms=int((time.perf_counter() - start_time) * 1000),
        )

    returning_registry: dict[Any, dict[str, Any]] = {}
    before_snapshots: dict[str, list[dict[str, Any]]] = {}
    after_snapshots: dict[str, list[dict[str, Any]]] = {}
    tables_affected: list[dict[str, Any]] = []
    total_rows = 0

    # 2. Begin single atomic transaction
    try:
        async with engine.begin() as conn:
            for idx, mut in enumerate(ordered_mutations):
                seq = mut.get("sequence", idx)
                op = mut.get("operation", "insert").lower()
                table = mut.get("table", "")

                # Resolve dynamic references
                resolved_mut = resolve_mutation_refs(mut, returning_registry)

                if op == "insert":
                    count = await _execute_insert(
                        conn=conn,
                        mutation=resolved_mut,
                        dialect=dialect,
                        returning_registry=returning_registry,
                        mutation_idx=idx,
                        mutation_seq=seq,
                    )
                    total_rows += count
                    tables_affected.append({
                        "table": table,
                        "operation": "insert",
                        "row_count": count,
                    })

                elif op == "patch":
                    cand_rows = (candidate_rows or {}).get(table) if candidate_rows else change_set.get("candidate_rows", {}).get(table)
                    count = await _execute_patch(
                        conn=conn,
                        mutation=resolved_mut,
                        dialect=dialect,
                        preview_row_counts=preview_row_counts,
                        before_snapshots=before_snapshots,
                        after_snapshots=after_snapshots,
                        candidate_rows=cand_rows,
                    )
                    total_rows += count
                    tables_affected.append({
                        "table": table,
                        "operation": "patch",
                        "row_count": count,
                    })

                else:
                    raise ValueError(f"Unsupported mutation operation '{op}'")

    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception("Atomic change-set transaction failed and rolled back: %s", exc)
        return ExecutionResult(
            success=False,
            total_rows_affected=0,
            tables_affected=tables_affected,
            before_snapshots=before_snapshots,
            after_snapshots=after_snapshots,
            error_message=str(exc),
            latency_ms=latency_ms,
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    # 3. Encrypt snapshots using Fernet
    before_encrypted = (
        encrypt_secret(json.dumps(before_snapshots)) if before_snapshots else None
    )
    after_encrypted = (
        encrypt_secret(json.dumps(after_snapshots)) if after_snapshots else None
    )

    return ExecutionResult(
        success=True,
        total_rows_affected=total_rows,
        tables_affected=tables_affected,
        before_snapshots=before_snapshots,
        after_snapshots=after_snapshots,
        before_snapshot_encrypted=before_encrypted,
        after_snapshot_encrypted=after_encrypted,
        returning_registry=returning_registry,
        latency_ms=latency_ms,
    )


async def execute_undo_change_set(
    engine: AsyncEngine,
    dialect: str,
    change_set: dict[str, Any],
    before_snapshots: dict[str, list[dict[str, Any]]],
    returning_registry: dict[Any, dict[str, Any]] | None = None,
) -> ExecutionResult:
    """Revert an executed change-set in reverse topological order within a single atomic transaction.

    - INSERT mutations: deleted by primary key.
    - PATCH mutations: restored to before_snapshot states.
    """
    start_time = time.perf_counter()
    raw_mutations = change_set.get("mutations", [])

    if not raw_mutations:
        return ExecutionResult(success=True, total_rows_affected=0)

    try:
        ordered_mutations = topological_sort_mutations(raw_mutations)
    except Exception as sort_err:
        return ExecutionResult(success=False, total_rows_affected=0, error_message=str(sort_err))

    # Reverse order: undo children before parents
    reverse_mutations = list(reversed(ordered_mutations))
    dialect_lower = dialect.lower()
    total_reverted = 0
    tables_affected: list[dict[str, Any]] = []

    try:
        async with engine.begin() as conn:
            for idx, mut in enumerate(reverse_mutations):
                table = mut.get("table", "")
                op = mut.get("operation", "insert").lower()
                seq = mut.get("sequence", idx)

                if op == "insert":
                    deleted_count = 0
                    rows = mut.get("rows", [])
                    reg = (returning_registry or {}).get(seq, {})

                    # If returned ID was registered:
                    if "id" in reg and reg["id"] is not None:
                        del_stmt = f"DELETE FROM {table} WHERE id = :target_id"
                        await conn.execute(text(del_stmt), {"target_id": reg["id"]})
                        deleted_count += 1
                    else:
                        for r in rows:
                            if "id" in r and r["id"] is not None:
                                del_stmt = f"DELETE FROM {table} WHERE id = :target_id"
                                await conn.execute(text(del_stmt), {"target_id": r["id"]})
                                deleted_count += 1
                            else:
                                where_parts = []
                                params = {}
                                for c_idx, (col, val) in enumerate(r.items()):
                                    p_name = f"d_{c_idx}"
                                    col_q = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
                                    where_parts.append(f"{col_q} = :{p_name}")
                                    params[p_name] = val
                                if where_parts:
                                    del_stmt = f"DELETE FROM {table} WHERE {' AND '.join(where_parts)}"
                                    await conn.execute(text(del_stmt), params)
                                    deleted_count += 1

                    total_reverted += deleted_count
                    tables_affected.append({"table": table, "operation": "undo_insert", "row_count": deleted_count})

                elif op == "patch":
                    restored_count = 0
                    snap_rows = before_snapshots.get(table, [])
                    if snap_rows:
                        for row in snap_rows:
                            if "id" in row and row["id"] is not None:
                                set_parts = []
                                params = {"pk_id": row["id"]}
                                for c_idx, (col, val) in enumerate(row.items()):
                                    if col == "id":
                                        continue
                                    p_name = f"s_{c_idx}"
                                    col_q = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
                                    set_parts.append(f"{col_q} = :{p_name}")
                                    params[p_name] = val
                                if set_parts:
                                    update_stmt = f"UPDATE {table} SET {', '.join(set_parts)} WHERE id = :pk_id"
                                    await conn.execute(text(update_stmt), params)
                                    restored_count += 1
                            else:
                                patch_filter = mut.get("filter", {})
                                set_parts = []
                                params = {}
                                for c_idx, (col, val) in enumerate(row.items()):
                                    p_name = f"s_{c_idx}"
                                    col_q = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
                                    set_parts.append(f"{col_q} = :{p_name}")
                                    params[p_name] = val
                                f_parts = []
                                for f_idx, (col, val) in enumerate(patch_filter.items()):
                                    p_name = f"f_{f_idx}"
                                    col_q = f'"{col}"' if dialect_lower != "mysql" else f"`{col}`"
                                    f_parts.append(f"{col_q} = :{p_name}")
                                    params[p_name] = val
                                if set_parts and f_parts:
                                    update_stmt = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(f_parts)}"
                                    await conn.execute(text(update_stmt), params)
                                    restored_count += 1

                    total_reverted += restored_count
                    tables_affected.append({"table": table, "operation": "undo_patch", "row_count": restored_count})

    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.exception("Undo transaction failed and rolled back: %s", exc)
        return ExecutionResult(
            success=False,
            total_rows_affected=0,
            tables_affected=tables_affected,
            error_message=str(exc),
            latency_ms=latency_ms,
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return ExecutionResult(
        success=True,
        total_rows_affected=total_reverted,
        tables_affected=tables_affected,
        latency_ms=latency_ms,
    )


def create_mutation_executor_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the LangGraph mutation execution node."""

    async def mutation_executor_node(state: AgentState) -> dict[str, Any]:
        """Execute the approved change-set in a single atomic transaction."""
        change_set = state.get("mutation_change_set")
        project_id = state["project_id"]
        session_id = state["session_id"]
        connection_id = state["connection_id"]

        logger.info(
            "--- [Node: mutation_executor] START ---\n"
            "  Session: %s\n"
            "  Project: %s",
            session_id,
            project_id,
        )

        if not change_set:
            return {
                "mutation_status": "FAILED",
                "execution_error": "No change-set proposal available for execution.",
            }

        engine = deps.connection_manager.get_engine(
            project_id=project_id,
            connection_id=connection_id,
            encrypted_connection_string=deps.connection.encrypted_connection_string,
        )

        exec_res = await execute_change_set(
            engine=engine,
            dialect=deps.connection.dialect,
            change_set=change_set,
        )

        if not exec_res.success:
            return {
                "mutation_status": "FAILED",
                "execution_error": exec_res.error_message,
                "nl_summary": f"Mutation execution failed: {exec_res.error_message}",
            }

        return {
            "mutation_status": "EXECUTED",
            "execution_result": exec_res.tables_affected,
            "nl_summary": (
                f"Successfully executed database transaction: {change_set.get('summary', '')}. "
                f"{exec_res.total_rows_affected} total row(s) affected."
            ),
        }

    return mutation_executor_node
