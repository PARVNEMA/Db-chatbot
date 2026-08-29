"""
Agent node — General conversation responder.

Handles non-query conversational interactions (e.g., greetings, questions about capabilities,
casual conversation) via direct LLM invocation without generating or executing SQL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.prompts import GENERAL_CONVERSATION_PROMPT
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_general_chat_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the general conversation response node."""

    async def general_chat_node(state: AgentState) -> dict[str, Any]:
        """Respond directly to general conversational queries."""
        user_query = state["user_query"]
        messages = GENERAL_CONVERSATION_PROMPT.format_messages(
            user_query=user_query,
            messages=state.get("messages", []),
        )

        logger.info(
            "Responding to general conversational query for project %s: '%s'",
            state["project_id"],
            user_query,
        )

        try:
            llm_response = await deps.llm.ainvoke(messages)
            summary = str(llm_response.content).strip()
        except Exception as exc:
            logger.error("General chat LLM invocation failed: %s", exc)
            summary = "Hello! I am your database assistant. How can I help you query or analyze your data today?"

        return {
            "nl_summary": summary,
            "generated_sql": "",
            "execution_result": [],
            "execution_error": None,
        }

    return general_chat_node
