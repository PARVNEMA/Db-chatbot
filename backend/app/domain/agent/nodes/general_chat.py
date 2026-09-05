"""
Agent node — General conversation responder.

Handles non-query conversational interactions by asking the user to submit a
database-related question, without generating or executing SQL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)

GENERAL_CHAT_REDIRECT_MESSAGE: str = (
    "I can help with database-related questions. Please ask about querying or analyzing your data."
)


def create_general_chat_node(
    _deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the general conversation response node."""

    async def general_chat_node(state: AgentState) -> dict[str, Any]:
        """Ask the user to submit a database-related question."""
        user_query = state.get("user_query", "")
        logger.info(
            "--- [Node: general_chat] INPUT ---\n"
            "  Query: %s",
            user_query,
        )

        logger.info(
            "--- [Node: general_chat] OUTPUT ---\n"
            "  Response: %s",
            GENERAL_CHAT_REDIRECT_MESSAGE,
        )

        return {
            "nl_summary": GENERAL_CHAT_REDIRECT_MESSAGE,
            "generated_sql": "",
            "execution_result": [],
            "execution_error": None,
        }

    return general_chat_node
