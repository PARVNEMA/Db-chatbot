"""Agent node — Unsafe intent handler.

Handles destructive or guardrail-breaking user queries (e.g. DROP, TRUNCATE, DELETE, ALTER, DDL/DML)
by immediately returning an explicit, helpful rejection message without generating or executing SQL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)

UNSAFE_REFUSAL_MESSAGE: str = (
    "⚠️ **This request cannot be processed.**\n\n"
    "I am a **read-only** database assistant. I cannot execute or help with operations "
    "that modify, delete, or destroy data or schema (such as `DROP`, `TRUNCATE`, `DELETE`, "
    "`INSERT`, `UPDATE`, `ALTER`, `CREATE`, `GRANT`, or `REVOKE`).\n\n"
    "Please ask me a **data query** or **analytics question** instead — "
    "for example:\n"
    "- *\"Show me the top 10 customers by revenue\"*\n"
    "- *\"What was the total order count last month?\"*\n"
    "- *\"List the columns in the orders table\"*"
)


def create_unsafe_handler_node() -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the unsafe/destructive intent response node."""

    async def unsafe_handler_node(state: AgentState) -> dict[str, Any]:
        """Return a firm refusal for unsafe/destructive intent."""
        user_query = state.get("user_query", "")
        logger.warning(
            "--- [Node: unsafe_handler] INPUT ---\n"
            "  Query: %s",
            user_query,
        )
        logger.warning(
            "--- [Node: unsafe_handler] OUTPUT ---\n"
            "  Action: Blocked destructive query",
        )
        return {
            "nl_summary": UNSAFE_REFUSAL_MESSAGE,
            "generated_sql": "",
            "execution_result": [],
            "execution_error": None,
        }

    return unsafe_handler_node
