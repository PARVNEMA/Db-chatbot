"""Agent domain — Mutation Planner Node (Phase 4).

Transforms user write/modification queries into strictly structured, type-safe
ChangeSetProposal proposals using LLM planning with compact writable schema context.
The LLM never generates executable DML SQL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.exceptions import BadRequestException
from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.mutation_schemas import ChangeSetProposal
from app.domain.agent.prompts import (
    MUTATION_PLANNER_PROMPT,
    parse_mutation_planner_response,
)
from app.domain.agent.state import AgentState
from app.domain.chat.rate_limiter import mutation_rate_limiter
from app.domain.schema_introspection.schemas import TableDetailResponse

logger = logging.getLogger(__name__)


def format_writable_schema_context(
    tables: list[TableDetailResponse],
    blocked_tables: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Format schema tables into a compact, token-efficient notation for mutation planning.

    Excludes tables in blocked_tables and clearly annotates:
    - [PRIMARY KEY]
    - [READ-ONLY] (identity, serial, generated, autoincrement)
    - [REQUIRED FOR INSERT] (non-nullable without defaults)
    - [REFERENCES target_table.target_column]

    Returns:
        A tuple of (structured_dict, compact_schema_text).
    """
    if not tables:
        return {}, "No writable tables available in schema."

    blocked_set = {b.lower() for b in (blocked_tables or [])}
    tables_map: dict[str, list[dict[str, Any]]] = {}
    schema_lines: list[str] = []

    for table in sorted(tables, key=lambda t: t.table_name):
        # Exclude blocked tables from writable schema context
        if table.table_name.lower() in blocked_set:
            continue

        col_list: list[dict[str, Any]] = []
        schema_lines.append(f"Table: {table.table_name}")

        for col in sorted(table.columns, key=lambda c: c.ordinal_position):
            col_info = {
                "name": col.column_name,
                "type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_read_only": col.is_read_only,
                "is_nullable": col.is_nullable,
                "is_foreign_key": col.is_foreign_key,
                "fk_target_table": col.fk_target_table,
                "fk_target_column": col.fk_target_column,
            }
            col_list.append(col_info)

            flags: list[str] = []
            if col.is_primary_key:
                flags.append("PRIMARY KEY")
            if col.is_read_only:
                flags.append("READ-ONLY")
            elif not col.is_nullable and not col.column_default:
                flags.append("REQUIRED FOR INSERT")

            if col.is_foreign_key and col.fk_target_table:
                target_col = col.fk_target_column or "id"
                flags.append(f"REFERENCES {col.fk_target_table}.{target_col}")

            flag_str = f" [{' | '.join(flags)}]" if flags else ""
            schema_lines.append(f"  - {col.column_name} ({col.data_type}){flag_str}")

        schema_lines.append("")
        tables_map[table.table_name] = col_list

    if not schema_lines:
        return {}, "All schema tables are currently blocked from write operations."

    return tables_map, "\n".join(schema_lines).strip()


def create_mutation_planner_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the mutation planner node for the LangGraph agent pipeline."""

    async def mutation_planner_node(state: AgentState) -> dict[str, Any]:
        """Formulate a structured ChangeSetProposal from user write query and writable schema."""
        user_query = state["user_query"]
        project_id = state["project_id"]

        logger.info(
            "--- [Node: mutation_planner] INPUT ---\n"
            "  Query: %s\n"
            "  Project: %s\n"
            "  Dialect: %s",
            user_query,
            project_id,
            deps.connection.dialect,
        )

        # 1. Verify writes_enabled master switch
        if not getattr(deps.connection, "writes_enabled", False):
            logger.warning("--- [Node: mutation_planner] Writes disabled on connection ---")
            refusal = (
                "Database write operations (INSERT / UPDATE) are currently disabled for this connection. "
                "Only the project owner can enable writes under connection settings."
            )
            return {
                "mutation_status": "writes_disabled",
                "mutation_validation_error": "Write operations are disabled for this database connection.",
                "mutation_change_set": None,
                "nl_summary": refusal,
            }

        # 1.5 Safety Rate Limits & Cooldown check (Phase 7)
        db_session = None
        try:
            db_session = getattr(deps, "db", None)
        except AttributeError:
            db_session = None

        if db_session is not None:
            try:
                await mutation_rate_limiter.check_all_write_limits(
                    db=db_session,
                    project_id=project_id,
                    session_id=state["session_id"],
                )
            except BadRequestException as rl_err:
                logger.warning("--- [Node: mutation_planner] Rate limit / cooldown blocked planning: %s ---", rl_err.detail)
                return {
                    "mutation_status": "rate_limited",
                    "mutation_validation_error": rl_err.detail,
                    "mutation_change_set": None,
                    "nl_summary": f"⚠️ **Write Limit Reached**: {rl_err.detail}",
                }

        # 2. Retrieve schema tables
        tables: list[TableDetailResponse] = []
        if deps.schema_service is not None:
            try:
                tables = await deps.schema_service.list_tables(
                    project_id=project_id,
                    user_id=deps.user_id,
                )
            except Exception as exc:
                logger.error("Failed to load schema tables for mutation planner: %s", exc)
                return {
                    "mutation_status": "planning_failed",
                    "mutation_validation_error": f"Failed to retrieve database schema: {exc}",
                    "mutation_change_set": None,
                    "nl_summary": "I was unable to retrieve the database schema to plan this change.",
                }

        # 3. Format compact writable schema context
        _, schema_context = format_writable_schema_context(
            tables=tables,
            blocked_tables=deps.connection.blocked_tables,
        )

        # 4. Invoke LLM to generate structured mutation proposal
        history = state.get("messages", [])
        messages = MUTATION_PLANNER_PROMPT.format_messages(
            sql_dialect=deps.connection.dialect,
            schema_context=schema_context,
            user_query=user_query,
            messages=history,
        )

        try:
            llm_response = await deps.llm.ainvoke(messages)
            raw_content = str(llm_response.content).strip()
            raw_proposal = parse_mutation_planner_response(raw_content)
            proposal = ChangeSetProposal.model_validate(raw_proposal)
        except Exception as exc:
            logger.warning("Mutation planning LLM generation or parsing failed: %s", exc)
            return {
                "mutation_status": "planning_failed",
                "mutation_validation_error": f"Failed to formulate a valid mutation proposal: {exc}",
                "mutation_change_set": None,
                "nl_summary": (
                    "I was unable to construct a valid change-set for your request. "
                    f"Details: {exc}"
                ),
            }

        # Handle case where LLM could not formulate mutations (e.g. missing filter/row info)
        if not proposal.mutations:
            logger.info("--- [Node: mutation_planner] Proposal contains 0 mutations: %s ---", proposal.summary)
            return {
                "mutation_status": "planning_failed",
                "mutation_validation_error": None,
                "mutation_change_set": None,
                "nl_summary": proposal.summary,
            }

        logger.info(
            "--- [Node: mutation_planner] PROPOSAL GENERATED ---\n"
            "  Summary: %s\n"
            "  Mutations: %d",
            proposal.summary,
            len(proposal.mutations),
        )

        return {
            "mutation_status": "planned",
            "mutation_change_set": proposal.model_dump(mode="json"),
            "mutation_validation_error": None,
            "nl_summary": proposal.summary,
        }

    return mutation_planner_node
