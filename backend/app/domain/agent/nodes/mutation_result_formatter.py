"""Agent domain — Mutation Result Formatter Node (Phase 4).

Formats validated mutation change-sets, validation errors, or write refusals
into a clear, human-readable natural language summary for the user.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_mutation_result_formatter_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the mutation result formatting node for write pipelines."""

    async def mutation_result_formatter_node(state: AgentState) -> dict[str, Any]:
        """Format the status and details of the planned mutation into nl_summary."""
        status = state.get("mutation_status")
        validation_error = state.get("mutation_validation_error")
        change_set = state.get("mutation_change_set")

        logger.info(
            "--- [Node: mutation_result_formatter] INPUT ---\n"
            "  Status: %s\n"
            "  Validation Error: %s",
            status,
            validation_error,
        )

        if status == "writes_disabled":
            msg = (
                "Database write operations (INSERT / UPDATE) are disabled for this connection. "
                "Only the project owner can enable writes under connection settings."
            )
            return {"nl_summary": msg}

        if status == "validation_failed" or validation_error:
            msg = f"Your requested database modification could not be approved due to validation errors:\n- {validation_error}"
            return {"nl_summary": msg}

        if status == "planning_failed":
            existing = state.get("nl_summary")
            msg = existing or "I was unable to formulate a valid mutation plan for your request."
            return {"nl_summary": msg}

        if change_set and status == "validated":
            summary = change_set.get("summary", "Proposed database modification")
            mutations = change_set.get("mutations", [])
            lines = [f"**Proposed Change-Set:** {summary}\n"]
            lines.append(f"**Total Affected Rows:** {change_set.get('expected_total_rows_affected', len(mutations))}")
            lines.append("\n**Planned Operations:**")

            for m in mutations:
                seq = m.get("sequence", 1)
                op = m.get("operation", "insert").upper()
                tbl = m.get("table", "unknown")
                rows = m.get("rows", [])
                cols = m.get("columns", [])
                lines.append(f"- **Step {seq}**: {op} into `{tbl}` ({len(rows)} row(s), columns: {', '.join(cols)})")
                if m.get("filter"):
                    lines.append(f"  *Filter:* `{m['filter']}`")
                if m.get("dependencies"):
                    lines.append(f"  *Depends on step(s):* {m['dependencies']}")

            lines.append("\n*The proposed change-set has passed all deterministic safety validations and is staged for approval.*")
            return {"nl_summary": "\n".join(lines)}

        existing_summary = state.get("nl_summary")
        return {"nl_summary": existing_summary or "Mutation processed."}

    return mutation_result_formatter_node
