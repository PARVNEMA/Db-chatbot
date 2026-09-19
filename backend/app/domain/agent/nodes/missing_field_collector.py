"""Agent domain — Missing Field Collector Node (Phase 5).

Inspects multi-table change-sets for missing required fields across all tables and rows,
and collects all missing values in a SINGLE interaction turn via WebSocket
('mutation_field_required' frame).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.state import AgentState
from app.domain.schema_introspection.schemas import TableDetailResponse

logger = logging.getLogger(__name__)


def find_missing_required_fields(
    change_set: dict[str, Any],
    tables: list[TableDetailResponse],
) -> list[dict[str, Any]]:
    """Scan all mutations and rows to identify every missing required column across the entire change-set.

    A column is required if:
    - is_read_only is False (not auto-increment, generated, or identity)
    - is_nullable is False (NOT NULL)
    - column_default is None (no default value expression)
    - Not already provided in row values
    - Not referencing a $ref dynamic dependency

    Returns:
        A list of missing field descriptor dictionaries compiled in one go.
    """
    table_map = {t.table_name.lower(): t for t in tables}
    all_missing: list[dict[str, Any]] = []

    mutations = change_set.get("mutations", [])
    for m in mutations:
        op = str(m.get("operation", "")).lower()
        # Missing field collection applies primarily to INSERT operations
        if op != "insert":
            continue

        table_name = m.get("table", "")
        tbl = table_map.get(table_name.lower())
        if not tbl:
            continue

        # Determine all required columns for this table
        required_cols = [
            col
            for col in tbl.columns
            if not col.is_read_only
            and not col.is_nullable
            and col.column_default is None
        ]

        rows = m.get("rows", [])
        for row_idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            row_data = row.get("values", row) if isinstance(row.get("values"), dict) else row
            for col in required_cols:
                col_name = col.column_name
                # Check if column is already provided
                val = row_data.get(col_name)
                if val is None:
                    # Case-insensitive lookup fallback
                    val = next(
                        (v for k, v in row_data.items() if k.lower() == col_name.lower()),
                        None,
                    )

                # If completely missing or None (for NOT NULL column)
                if val is None:
                    field_key = f"{table_name}[{row_idx}].{col_name}"
                    all_missing.append(
                        {
                            "table": table_name,
                            "row_index": row_idx,
                            "column": col_name,
                            "data_type": col.data_type,
                            "field_key": field_key,
                            "description": (
                                f"Required column '{col_name}' ({col.data_type}) for "
                                f"table '{table_name}' (row {row_idx + 1})"
                            ),
                        }
                    )

    return all_missing


def create_missing_field_collector_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the interactive missing field collector node."""

    async def missing_field_collector_node(state: AgentState) -> dict[str, Any]:
        """Detect all missing required fields across the proposal in one go and notify the client."""
        change_set = state.get("mutation_change_set")
        project_id = state["project_id"]
        session_id = state["session_id"]

        logger.info(
            "--- [Node: missing_field_collector] INPUT ---\n"
            "  Session: %s\n"
            "  Project: %s\n"
            "  Has Change-set: %s",
            session_id,
            project_id,
            bool(change_set),
        )

        if not change_set:
            return {
                "mutation_status": "planning_failed",
                "mutation_validation_error": "No change-set proposal available for field inspection.",
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
                logger.error("Failed to load schema tables for missing field collector: %s", exc)
                return {
                    "mutation_status": "planning_failed",
                    "mutation_validation_error": f"Schema retrieval failed: {exc}",
                }

        # Find ALL missing required fields in one go
        missing_fields = find_missing_required_fields(change_set, tables)

        if missing_fields:
            logger.info(
                "--- [Node: missing_field_collector] %d MISSING FIELDS DETECTED IN ONE GO ---",
                len(missing_fields),
            )

            # Broadcast a single WebSocket frame with all missing fields
            if deps.ws_manager is not None:
                await deps.ws_manager.send_event(
                    session_id=session_id,
                    event_type="mutation_field_required",
                    data={
                        "session_id": str(session_id),
                        "missing_fields": missing_fields,
                        "message": (
                            f"Please provide values for the following {len(missing_fields)} "
                            "required field(s) to continue."
                        ),
                    },
                )

            # Construct human-readable summary listing all missing fields
            lines = [
                f"To continue, the database requires values for the following **{len(missing_fields)} missing field(s)**:\n"
            ]
            for f in missing_fields:
                lines.append(f"- **{f['table']}.{f['column']}** (`{f['data_type']}`)")

            lines.append(
                "\nPlease provide these values in your next message or response to proceed with the mutation."
            )

            return {
                "mutation_status": "COLLECTING_INPUT",
                "mutation_fields_pending": [f["field_key"] for f in missing_fields],
                "nl_summary": "\n".join(lines),
            }

        logger.info("--- [Node: missing_field_collector] ALL REQUIRED FIELDS SATISFIED ---")
        return {
            "mutation_status": "input_complete",
            "mutation_fields_pending": [],
        }

    return missing_field_collector_node
