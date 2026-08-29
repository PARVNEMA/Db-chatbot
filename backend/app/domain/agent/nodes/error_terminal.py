"""
Agent node — Error Terminal node for graceful failure handling.

Invoked when the self-correction loop exceeds the maximum allowed retries (3).
Provides a clear, user-friendly explanation of why the query could not be executed.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)


async def error_terminal_node(state: AgentState) -> dict[str, Any]:
    """Provide a user-friendly error response after exhausting self-correction retries."""
    last_error = state.get("execution_error") or "An unexpected execution error occurred."
    retry_count = state.get("retry_count", 0)

    logger.warning(
        "Self-correction exhausted after %d retries for project %s. Last error: %s",
        retry_count,
        state["project_id"],
        last_error,
    )

    summary = (
        f"I was unable to successfully execute a query to answer your question after {retry_count} attempts. "
        f"The database reported the following issue: {last_error}. "
        "Please try rephrasing your question or checking if the required tables and columns exist in your schema."
    )

    return {
        "nl_summary": summary,
    }
