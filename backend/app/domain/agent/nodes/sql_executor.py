"""
Agent node — Guardrailed SQL execution (Phase 6).

Responsibilities:
1. Enforce AST-level read-only verification before execution.
2. Acquire tenant database session via ConnectionManager.
3. Execute SQL safely with row limit caps and timeout limits.
4. Capture execution results or record detailed error metadata for self-correction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.sql_validator import validate_read_only
from app.domain.agent.state import AgentState
from app.domain.connections.manager import QUERY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def create_sql_executor_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the guardrailed SQL execution node."""

    async def sql_executor_node(state: AgentState) -> dict[str, Any]:
        """Execute the generated SQL against the tenant database with read-only guardrails."""
        sql = state.get("generated_sql", "").strip()
        sql_dialect = state.get("sql_dialect") or deps.connection.dialect
        retry_count = state.get("retry_count", 0)
        error_history = list(state.get("error_history", []))

        if not sql:
            err_msg = "No SQL query was generated."
            logger.warning("SQL execution skipped: %s", err_msg)
            return {
                "execution_result": [],
                "execution_error": err_msg,
                "retry_count": retry_count + 1,
                "error_history": [*error_history, f"Attempt {retry_count + 1}: {err_msg}"],
            }

        # 1. AST-level read-only validation
        try:
            validate_read_only(sql, dialect=sql_dialect)
        except ValueError as val_err:
            err_msg = str(val_err)
            logger.warning("SQL failed read-only validation: %s", err_msg)
            return {
                "execution_result": [],
                "execution_error": err_msg,
                "retry_count": retry_count + 1,
                "error_history": [*error_history, f"Attempt {retry_count + 1} validation error: {err_msg}"],
            }

        # 2. Execute SQL via ConnectionManager
        session = deps.connection_manager.get_session(
            project_id=state["project_id"],
            connection_id=state["connection_id"],
            encrypted_connection_string=deps.connection.encrypted_connection_string,
        )

        try:
            async with session:
                rows = await deps.connection_manager.execute_safe(
                    session=session,
                    sql=sql,
                    timeout_seconds=QUERY_TIMEOUT_SECONDS,
                )
                logger.info(
                    "SQL executed successfully for project %s. Rows returned: %d",
                    state["project_id"],
                    len(rows),
                )
                return {
                    "execution_result": rows,
                    "execution_error": None,
                }
        except Exception as exc:
            err_str = str(exc)
            logger.warning(
                "SQL execution failed on target database for project %s: %s",
                state["project_id"],
                err_str,
            )
            return {
                "execution_result": [],
                "execution_error": err_str,
                "retry_count": retry_count + 1,
                "error_history": [*error_history, f"Attempt {retry_count + 1} execution error: {err_str}"],
            }

    return sql_executor_node
