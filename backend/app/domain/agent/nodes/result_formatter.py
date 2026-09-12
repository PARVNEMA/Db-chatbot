"""
Agent node — Natural language result summarization (Phase 7).

Responsibilities:
1. Review raw execution result rows and format human-friendly response.
2. Answer the user's specific natural language question clearly.
3. Summarize key numbers, totals, or trends while respecting token limits.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.prompts import RESULT_SUMMARY_PROMPT
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)

# Max result rows to pass to LLM summarizer to keep prompt concise
MAX_PROMPT_ROWS = 15


def _toon_scalar(value: Any) -> str:
    """Encode a flat scalar using TOON's CSV-like value representation."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    if any(character in text for character in (",", "\n", "\r", '"')):
        return json.dumps(text, ensure_ascii=False)
    return text


def _serialize_query_results(rows: list[dict[str, Any]]) -> str:
    """Serialize uniform flat rows as TOON, with compact JSON as a safe fallback."""
    if not rows:
        return "query_results[0]{}:"

    fields = list(rows[0])
    if not all(list(row) == fields for row in rows):
        return json.dumps(rows, default=str, separators=(",", ":"))

    if any(
        isinstance(value, (dict, list, tuple, set))
        for row in rows
        for value in row.values()
    ):
        return json.dumps(rows, default=str, separators=(",", ":"))

    header = "query_results[{}]{{{}}}:".format(len(rows), ",".join(fields))
    values = [
        ",".join(_toon_scalar(row[field]) for field in fields)
        for row in rows
    ]
    return "\n".join([header, *(f"  {row}" for row in values)])


def create_result_formatter_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the natural language result formatting node."""

    async def result_formatter_node(state: AgentState) -> dict[str, Any]:
        """Convert query results into plain-English summary answering the user query."""
        user_query = state["user_query"]
        generated_sql = state.get("generated_sql", "")
        execution_result = state.get("execution_result", [])
        row_count = len(execution_result)

        logger.info(
            "--- [Node: result_formatter] INPUT ---\n"
            "  Query: %s\n"
            "  Generated SQL: %s\n"
            "  Total Rows: %d",
            user_query,
            generated_sql,
            row_count,
        )

        sample_rows = execution_result[:MAX_PROMPT_ROWS]
        results_str = _serialize_query_results(sample_rows)

        messages = RESULT_SUMMARY_PROMPT.format_messages(
            user_query=user_query,
            generated_sql=generated_sql,
            row_count=row_count,
            query_results=results_str,
            messages=state.get("messages", [])[-6:],
        )

        try:
            llm_response = await deps.llm.ainvoke(messages)
            summary = str(llm_response.content).strip()
        except Exception as exc:
            logger.error("Result formatter LLM call failed: %s", exc)
            if row_count == 0:
                summary = "The query completed successfully, but no matching records were found."
            else:
                summary = f"The query returned {row_count} record(s)."

        logger.info(
            "--- [Node: result_formatter] OUTPUT ---\n"
            "  Summary:\n    %s",
            summary,
        )

        return {
            "nl_summary": summary,
        }

    return result_formatter_node
