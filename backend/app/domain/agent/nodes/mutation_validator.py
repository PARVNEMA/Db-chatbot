"""Agent domain — Deterministic Mutation Validator Node & Engine (Phase 3).

Enforces strict pre-execution safety rules, row caps, column writeability,
table denylists, primary key requirements for PATCH, circular dependency checks,
and foreign key validation before any mutation approval is requested.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Coroutine
from datetime import date, datetime
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.mutation_schemas import (
    ChangeSetProposal,
    MutationItem,
    MutationValidationResult,
    ValidationErrorItem,
)
from app.domain.agent.state import AgentState
from app.domain.connections.manager import ConnectionManager
from app.domain.connections.models import Connection
from app.domain.schema_introspection.schemas import ColumnResponse, TableDetailResponse

logger = logging.getLogger(__name__)

# Regex for parsing cross-table $ref expressions: $ref:mutations[0].returning.id
_REF_PATTERN = re.compile(
    r"^\$ref:mutations\[(\d+)\]\.returning\.([a-zA-Z_]\w*)$"
)


def _check_circular_dependencies(
    mutations: list[MutationItem],
) -> bool:
    """Check for circular dependencies using cycle detection (DFS with coloring).

    Returns:
        True if a circular dependency is detected, False otherwise.
    """
    n = len(mutations)
    adj: dict[int, set[int]] = {i: set() for i in range(n)}

    for i, m in enumerate(mutations):
        # Explicit declared dependencies
        for dep in m.dependencies:
            if 0 <= dep < n and dep != i:
                adj[i].add(dep)

        # Inferred dependencies from $ref references in rows
        for row in m.rows:
            if not isinstance(row, dict):
                continue
            for val in row.values():
                if isinstance(val, str):
                    match = _REF_PATTERN.match(val.strip())
                    if match:
                        ref_idx = int(match.group(1))
                        if 0 <= ref_idx < n and ref_idx != i:
                            adj[i].add(ref_idx)

    # 0 = unvisited (white), 1 = visiting (gray), 2 = visited (black)
    visited = [0] * n

    def has_cycle(u: int) -> bool:
        visited[u] = 1
        for v in adj[u]:
            if visited[v] == 1:
                return True
            if visited[v] == 0 and has_cycle(v):
                return True
        visited[u] = 2
        return False

    for node in range(n):
        if visited[node] == 0:
            if has_cycle(node):
                return True

    return False


def _validate_type_coercion(
    val: Any,
    data_type: str,
    col_name: str,
    table_name: str,
) -> ValidationErrorItem | None:
    """Validate that a literal value can be coerced to the expected column data type."""
    if val is None:
        return None

    # $ref values are deferred and evaluated at runtime
    if isinstance(val, str) and val.strip().startswith("$ref:"):
        return None

    dt = data_type.lower()

    # Integer types
    if any(it in dt for it in ("int", "serial", "bigint", "smallint")):
        if isinstance(val, bool):
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' (bool) for column '{col_name}' cannot be coerced to integer type '{data_type}'.",
            )
        try:
            int(val)
        except (ValueError, TypeError):
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' for column '{col_name}' cannot be coerced to expected type '{data_type}'.",
            )

    # Floating point / Numeric
    elif any(ft in dt for ft in ("float", "double", "real", "numeric", "decimal")):
        if isinstance(val, bool):
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' (bool) for column '{col_name}' cannot be coerced to numeric type '{data_type}'.",
            )
        try:
            float(val)
        except (ValueError, TypeError):
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' for column '{col_name}' cannot be coerced to expected type '{data_type}'.",
            )

    # Boolean
    elif any(bt in dt for bt in ("bool", "boolean")):
        if isinstance(val, str):
            if val.lower() not in ("true", "false", "1", "0", "t", "f", "yes", "no"):
                return ValidationErrorItem(
                    field=col_name,
                    table=table_name,
                    code="TYPE_COERCION_ERROR",
                    message=f"Value '{val}' for column '{col_name}' cannot be coerced to boolean.",
                )
        elif not isinstance(val, (bool, int)):
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' for column '{col_name}' cannot be coerced to boolean.",
            )

    # Date / Timestamp
    elif any(tt in dt for tt in ("date", "time", "timestamp")):
        if isinstance(val, (datetime, date)):
            return None
        if isinstance(val, str):
            try:
                # Try ISO format parsing
                datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                # Also try basic YYYY-MM-DD
                try:
                    date.fromisoformat(val)
                except ValueError:
                    return ValidationErrorItem(
                        field=col_name,
                        table=table_name,
                        code="TYPE_COERCION_ERROR",
                        message=f"Value '{val}' for column '{col_name}' is not a valid ISO date/timestamp format.",
                    )
        else:
            return ValidationErrorItem(
                field=col_name,
                table=table_name,
                code="TYPE_COERCION_ERROR",
                message=f"Value '{val}' for column '{col_name}' cannot be coerced to date/time type '{data_type}'.",
            )

    return None


async def validate_mutation_proposal(
    change_set: ChangeSetProposal | dict[str, Any],
    connection: Connection,
    tables: list[TableDetailResponse],
    manager: ConnectionManager | None = None,
) -> MutationValidationResult:
    """Deterministically validate a proposed write change-set against connection policies and schema metadata.

    Args:
        change_set: The structured proposal (ChangeSetProposal or raw dict).
        connection: Connection entity containing write policy flags and caps.
        tables: Introspected schema metadata for the target database.
        manager: Optional ConnectionManager instance for live FK checks.

    Returns:
        MutationValidationResult indicating validity and enumerating any violations.
    """
    errors: list[ValidationErrorItem] = []
    warnings: list[str] = []

    # 1. Parse ChangeSetProposal
    if isinstance(change_set, dict):
        try:
            proposal = ChangeSetProposal.model_validate(change_set)
        except Exception as exc:
            return MutationValidationResult(
                is_valid=False,
                errors=[
                    ValidationErrorItem(
                        code="SCHEMA_VALIDATION_ERROR",
                        message=f"Change-set proposal schema is malformed: {exc}",
                    )
                ],
            )
    else:
        proposal = change_set

    # 2. Master switch: writes_enabled check
    if not connection.writes_enabled:
        return MutationValidationResult(
            is_valid=False,
            errors=[
                ValidationErrorItem(
                    code="WRITES_DISABLED",
                    message="Write operations are disabled for this connection.",
                )
            ],
        )

    # 3. Check mutation count
    if not proposal.mutations:
        return MutationValidationResult(
            is_valid=False,
            errors=[
                ValidationErrorItem(
                    code="EMPTY_CHANGESET",
                    message="Change-set does not contain any mutations.",
                )
            ],
        )

    # Index schema tables & columns (case-insensitive)
    table_map: dict[str, TableDetailResponse] = {
        t.table_name.lower(): t for t in tables
    }
    col_map: dict[str, dict[str, ColumnResponse]] = {
        t.table_name.lower(): {c.column_name.lower(): c for c in t.columns}
        for t in tables
    }

    # 4. Table count cap check
    distinct_tables = {m.table.lower() for m in proposal.mutations}
    if len(distinct_tables) > connection.max_tables_per_changeset:
        errors.append(
            ValidationErrorItem(
                code="MAX_TABLES_EXCEEDED",
                message=(
                    f"Change-set touches {len(distinct_tables)} distinct tables, "
                    f"exceeding maximum allowed of {connection.max_tables_per_changeset}."
                ),
            )
        )

    # 5. Total rows cap check
    total_proposed_rows = 0
    for m in proposal.mutations:
        if m.operation == "insert":
            total_proposed_rows += len(m.rows)
        elif m.operation == "patch":
            total_proposed_rows += len(m.rows) if m.rows else 1

    if total_proposed_rows > connection.max_total_rows_per_changeset:
        errors.append(
            ValidationErrorItem(
                code="MAX_TOTAL_ROWS_EXCEEDED",
                message=(
                    f"Change-set proposes {total_proposed_rows} total rows, "
                    f"exceeding maximum allowed of {connection.max_total_rows_per_changeset}."
                ),
            )
        )

    # 6. Blocked tables check
    blocked_set = {b.lower() for b in (connection.blocked_tables or [])}
    for m in proposal.mutations:
        if m.table.lower() in blocked_set:
            errors.append(
                ValidationErrorItem(
                    table=m.table,
                    code="TABLE_BLOCKED",
                    message=f"Table '{m.table}' is blocked from write operations by connection policy.",
                )
            )

    # 7. Circular dependency check
    if _check_circular_dependencies(proposal.mutations):
        errors.append(
            ValidationErrorItem(
                code="CIRCULAR_DEPENDENCY",
                message="Circular dependency detected among mutations in change-set.",
            )
        )

    # 8. Per-mutation detailed checks
    for idx, m in enumerate(proposal.mutations):
        tbl = table_map.get(m.table.lower())
        table_cols = col_map.get(m.table.lower(), {})

        # Operation validity
        if m.operation not in ("insert", "patch"):
            errors.append(
                ValidationErrorItem(
                    table=m.table,
                    code="INVALID_OPERATION",
                    message=f"Unsupported operation '{m.operation}'. Only 'insert' and 'patch' are permitted.",
                )
            )
            continue

        # Table existence check
        if not tbl:
            errors.append(
                ValidationErrorItem(
                    table=m.table,
                    code="TABLE_NOT_FOUND",
                    message=f"Table '{m.table}' does not exist in the database schema.",
                )
            )
            continue

        # Row caps per table
        if m.operation == "insert":
            row_count = len(m.rows)
            if row_count == 0:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        code="EMPTY_INSERT_ROWS",
                        message=f"INSERT mutation on table '{m.table}' must contain at least one row.",
                    )
                )
            elif row_count > connection.max_insert_rows_per_table:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        code="MAX_INSERT_ROWS_EXCEEDED",
                        message=(
                            f"Table '{m.table}' specifies {row_count} insert rows, "
                            f"exceeding per-table limit of {connection.max_insert_rows_per_table}."
                        ),
                    )
                )

        elif m.operation == "patch":
            row_count = len(m.rows) if m.rows else 1
            if row_count > connection.max_patch_rows_per_table:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        code="MAX_PATCH_ROWS_EXCEEDED",
                        message=(
                            f"Table '{m.table}' specifies {row_count} patch rows, "
                            f"exceeding per-table limit of {connection.max_patch_rows_per_table}."
                        ),
                    )
                )

            # PATCH requires primary key
            has_pk = any(c.is_primary_key for c in tbl.columns)
            if not has_pk:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        code="PATCH_TABLE_NO_PK",
                        message=f"Table '{m.table}' cannot be updated because it does not have a primary key.",
                    )
                )

            # PATCH requires filter / where condition
            has_filter = bool(m.filter)
            if not has_filter and m.rows:
                # Check if rows contain a filter or primary key condition
                has_filter = any(
                    isinstance(r, dict) and ("filter" in r or any(table_cols.get(k.lower(), ColumnResponse.model_construct()).is_primary_key for k in r))
                    for r in m.rows
                )
            if not has_filter:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        code="PATCH_MISSING_FILTER",
                        message=f"PATCH operation on table '{m.table}' requires a non-empty filter condition.",
                    )
                )

        # 9. Column existence & writeability checks
        # Gather all targeted column names
        targeted_columns: set[str] = set(m.columns)
        for row in m.rows:
            if isinstance(row, dict):
                # If row is shaped as {"values": {...}, "filter": {...}}
                row_vals = row.get("values", row) if isinstance(row.get("values"), dict) else row
                for col_name in row_vals:
                    if col_name not in ("filter", "values", "updates"):
                        targeted_columns.add(col_name)

        for col_name in targeted_columns:
            col_meta = table_cols.get(col_name.lower())
            if not col_meta:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        field=col_name,
                        code="COLUMN_NOT_FOUND",
                        message=f"Column '{col_name}' does not exist on table '{m.table}'.",
                    )
                )
                continue

            # Check writeability (is_read_only = True for generated/identity/autoincrement)
            if col_meta.is_read_only:
                errors.append(
                    ValidationErrorItem(
                        table=m.table,
                        field=col_name,
                        code="READ_ONLY_COLUMN",
                        message=(
                            f"Column '{col_name}' on table '{m.table}' is read-only "
                            "(auto-increment, identity, or generated) and cannot be modified."
                        ),
                    )
                )

        # 10. Type coercion & $ref validation across row values
        for _row_idx, row in enumerate(m.rows):
            if not isinstance(row, dict):
                continue
            row_vals = row.get("values", row) if isinstance(row.get("values"), dict) else row
            for col_name, val in row_vals.items():
                if col_name in ("filter", "values", "updates"):
                    continue

                col_meta = table_cols.get(col_name.lower())
                if not col_meta:
                    continue

                # Check if value is a $ref reference
                if isinstance(val, str) and val.strip().startswith("$ref:"):
                    ref_match = _REF_PATTERN.match(val.strip())
                    if not ref_match:
                        errors.append(
                            ValidationErrorItem(
                                table=m.table,
                                field=col_name,
                                code="INVALID_REF_SYNTAX",
                                message=(
                                    f"Invalid $ref syntax '{val}' for column '{col_name}'. "
                                    "Expected format: '$ref:mutations[N].returning.<column>'."
                                ),
                            )
                        )
                    else:
                        ref_seq = int(ref_match.group(1))
                        ref_col = ref_match.group(2)
                        if ref_seq >= len(proposal.mutations) or ref_seq < 0:
                            errors.append(
                                ValidationErrorItem(
                                    table=m.table,
                                    field=col_name,
                                    code="REF_TARGET_OUT_OF_BOUNDS",
                                    message=(
                                        f"Reference '{val}' points to mutation index {ref_seq}, "
                                        f"which is out of bounds (total mutations: {len(proposal.mutations)})."
                                    ),
                                )
                            )
                        elif ref_seq == idx:
                            errors.append(
                                ValidationErrorItem(
                                    table=m.table,
                                    field=col_name,
                                    code="SELF_REFERENTIAL_REF",
                                    message=f"Mutation at index {idx} cannot reference its own returning column in '{val}'.",
                                )
                            )
                        else:
                            # Verify target mutation table has the referenced returning column
                            target_mutation = proposal.mutations[ref_seq]
                            target_table_cols = col_map.get(target_mutation.table.lower(), {})
                            if target_table_cols and ref_col.lower() not in target_table_cols:
                                errors.append(
                                    ValidationErrorItem(
                                        table=m.table,
                                        field=col_name,
                                        code="REF_TARGET_COLUMN_NOT_FOUND",
                                        message=(
                                            f"Reference '{val}' targets column '{ref_col}' which does "
                                            f"not exist on referenced table '{target_mutation.table}'."
                                        ),
                                    )
                                )
                    continue

                # Validate literal value type coercion
                type_err = _validate_type_coercion(
                    val=val,
                    data_type=col_meta.data_type,
                    col_name=col_name,
                    table_name=m.table,
                )
                if type_err:
                    errors.append(type_err)

    return MutationValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        total_rows=total_proposed_rows,
        table_names=sorted(distinct_tables),
    )


def create_mutation_validator_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the mutation validator node for the LangGraph agent pipeline."""

    async def mutation_validator_node(state: AgentState) -> dict[str, Any]:
        """Validate proposed change-set in agent state deterministically."""
        change_set = state.get("mutation_change_set")
        project_id = state["project_id"]

        logger.info(
            "--- [Node: mutation_validator] INPUT ---\n"
            "  Project: %s\n"
            "  Change-set: %s",
            project_id,
            bool(change_set),
        )

        if not change_set:
            return {
                "mutation_status": "validation_failed",
                "mutation_validation_error": "No mutation proposal found in state to validate.",
            }

        # Fetch introspected schema tables
        tables: list[TableDetailResponse] = []
        if deps.schema_service is not None:
            try:
                tables = await deps.schema_service.list_tables(
                    project_id=project_id,
                    user_id=deps.user_id,
                )
            except Exception as exc:
                logger.error("Failed to load schema tables for mutation validation: %s", exc)
                return {
                    "mutation_status": "validation_failed",
                    "mutation_validation_error": f"Schema metadata retrieval failed: {exc}",
                }

        result = await validate_mutation_proposal(
            change_set=change_set,
            connection=deps.connection,
            tables=tables,
            manager=deps.connection_manager,
        )

        if not result.is_valid:
            logger.warning(
                "--- [Node: mutation_validator] VALIDATION FAILED ---\n"
                "  Errors: %s",
                result.error_summary,
            )
            return {
                "mutation_status": "validation_failed",
                "mutation_validation_error": result.error_summary,
            }

        logger.info(
            "--- [Node: mutation_validator] VALIDATION PASSED ---\n"
            "  Tables: %s\n"
            "  Total Rows: %d",
            result.table_names,
            result.total_rows,
        )
        return {
            "mutation_status": "validated",
            "mutation_validation_error": None,
        }

    return mutation_validator_node
