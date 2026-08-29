"""
Agent node — Dialect-aware SQL generation and self-correction (Phase 5).

Responsibilities:
1. Generate syntactically valid, dialect-compliant SQL using LLM.
2. Incorporate conversational message history for multi-turn context.
3. Automatically switch to self-correction prompt on retry attempts.
4. Extract clean SQL from LLM response.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.prompts import (
    SQL_CORRECTION_PROMPT,
    SQL_GENERATION_PROMPT,
    extract_clean_sql,
)
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_sql_generator_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the SQL generation and self-correction node."""

    async def sql_generator_node(state: AgentState) -> dict[str, Any]:
        """Generate or correct a SQL query based on state and error feedback."""
        user_query = state["user_query"]
        sql_dialect = state.get("sql_dialect") or deps.connection.dialect or "postgresql"
        schema_context = state.get("schema_context", "")
        intent_type = state.get("intent_type", "general")
        execution_error = state.get("execution_error")
        retry_count = state.get("retry_count", 0)
        error_history = state.get("error_history", [])
        failed_sql = state.get("generated_sql", "")

        is_retry = bool(execution_error and retry_count > 0)

        if is_retry:
            logger.info(
                "Self-correction retry #%d for project %s. Error: %s",
                retry_count,
                state["project_id"],
                execution_error,
            )
            history_str = "\n".join(error_history) if error_history else execution_error or "None"
            messages = SQL_CORRECTION_PROMPT.format_messages(
                schema_context=schema_context or "No schema available.",
                sql_dialect=sql_dialect,
                user_query=user_query,
                failed_sql=failed_sql,
                error_message=execution_error or "Unknown error",
                error_history=history_str,
            )
        else:
            logger.info(
                "Generating initial SQL for project %s with dialect %s",
                state["project_id"],
                sql_dialect,
            )
            messages = SQL_GENERATION_PROMPT.format_messages(
                schema_context=schema_context or "No schema available.",
                intent_type=intent_type,
                sql_dialect=sql_dialect,
                user_query=user_query,
                messages=state.get("messages", []),
            )

        try:
            llm_response = await deps.llm.ainvoke(messages)
            raw_content = str(llm_response.content).strip()
            clean_sql = extract_clean_sql(raw_content)
        except Exception as exc:
            logger.error("SQL generation LLM call failed: %s", exc)
            clean_sql = ""

        return {
            "generated_sql": clean_sql,
            "sql_dialect": sql_dialect,
        }

    return sql_generator_node
