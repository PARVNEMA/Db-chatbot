"""
Agent node — Intent classification and semantic schema linking (Phase 4).

Responsibilities:
1. Classify query intent: lookup | aggregation | comparison | trend | general.
2. Extract domain entities and build semantic search query.
3. Retrieve relevant schema tables/columns via EmbeddingService vector similarity search.
4. Format structured schema context for downstream SQL generation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.guardrail import detect_unsafe_intent
from app.domain.agent.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    parse_intent_classification_response,
)
from app.domain.agent.state import AgentState
from app.domain.embeddings.schemas import SchemaSearchResult

logger = logging.getLogger(__name__)


def format_schema_context_from_results(
    search_results: list[SchemaSearchResult],
) -> tuple[dict[str, Any], str]:
    """Format vector search schema results into structured dict and prompt string.

    The output string includes:
    - A per-table column listing with PK/FK annotations.
    - A dedicated "Relationships" section summarising all FK join paths so the
      LLM can construct correct JOINs without guessing.
    """
    if not search_results:
        return {}, ""

    # Group by table
    tables_map: dict[str, list[dict[str, Any]]] = {}
    for res in search_results:
        col_info = {
            "name": res.column_name,
            "type": res.data_type,
            "is_primary_key": res.is_primary_key,
            "is_foreign_key": res.is_foreign_key,
            "fk_target_table": res.fk_target_table,
            "fk_target_column": res.fk_target_column,
        }
        tables_map.setdefault(res.table_name, []).append(col_info)

    schema_lines: list[str] = []
    join_hints: list[str] = []

    for table_name, cols in sorted(tables_map.items()):
        schema_lines.append(f"Table: {table_name}")
        schema_lines.append("Columns:")
        for col in cols:
            flags: list[str] = []
            if col["is_primary_key"]:
                flags.append("PRIMARY KEY")
            if col["is_foreign_key"] and col["fk_target_table"]:
                target_col = col["fk_target_column"] or "id"
                fk_ref = f"REFERENCES {col['fk_target_table']}.{target_col}"
                flags.append(fk_ref)
                # Collect join hint: "table.col -> fk_target_table.target_col"
                join_hints.append(
                    f"  {table_name}.{col['name']} -> {col['fk_target_table']}.{target_col}"
                    f"  (JOIN {col['fk_target_table']} ON {table_name}.{col['name']} = {col['fk_target_table']}.{target_col})"
                )

            flag_str = f" [{' | '.join(flags)}]" if flags else ""
            schema_lines.append(f"  - {col['name']} ({col['type']}){flag_str}")
        schema_lines.append("")

    # Append a clear Relationships block if any FK links were found
    if join_hints:
        schema_lines.append("Relationships (use these JOIN paths to fetch human-readable fields):")
        schema_lines.extend(join_hints)
        schema_lines.append("")

    return tables_map, "\n".join(schema_lines).strip()


def create_intent_node(
    deps: GraphDependencies,
) -> Callable[[AgentState], Coroutine[Any, Any, dict[str, Any]]]:
    """Factory creating the intent classification and schema retrieval node."""

    async def intent_node(state: AgentState) -> dict[str, Any]:
        """Classify user query intent and retrieve relevant schema context via vector search."""
        user_query = state["user_query"]
        project_id = state["project_id"]

        logger.info(
            "--- [Node: intent] INPUT ---\n"
            "  Query: %s\n"
            "  Project: %s",
            user_query,
            project_id,
        )

        # 1. Deterministic pre-classification guardrail check
        matched_unsafe = detect_unsafe_intent(user_query)
        if matched_unsafe:
            logger.warning(
                "--- [Node: intent] OUTPUT (Guardrail Blocked) ---\n"
                "  Intent: unsafe (pattern: '%s')",
                matched_unsafe,
            )
            return {
                "intent_type": "unsafe",
                "extracted_entities": [],
                "relevant_schema": {},
                "schema_context": "",
            }

        # 2. Classify intent via LLM
        messages = INTENT_CLASSIFICATION_PROMPT.format_messages(user_query=user_query)
        try:
            llm_response = await deps.llm.ainvoke(messages)
            raw_content = str(llm_response.content).strip()
            parsed_intent = parse_intent_classification_response(raw_content)
        except Exception as exc:
            logger.warning("LLM intent classification failed (%s); using default.", exc)
            parsed_intent = {
                "intent_type": "general",
                "extracted_entities": [],
                "search_query": user_query,
            }

        intent_type = parsed_intent["intent_type"]
        extracted_entities = parsed_intent["extracted_entities"]
        search_query = parsed_intent.get("search_query") or user_query

        # If LLM classified intent as unsafe, immediately short-circuit without schema search
        if intent_type == "unsafe":
            logger.warning(
                "--- [Node: intent] OUTPUT (LLM Blocked) ---\n"
                "  Intent: unsafe\n"
                "  Entities: %s",
                extracted_entities,
            )
            return {
                "intent_type": "unsafe",
                "extracted_entities": extracted_entities,
                "relevant_schema": {},
                "schema_context": "",
            }

        # 3. Retrieve schema context strictly via vector similarity search
        relevant_schema: dict[str, Any] = {}
        schema_context: str = ""

        try:
            search_results = await deps.embedding_service.search_schema(
                project_id=project_id,
                user_id=deps.user_id,
                query=search_query,
            )
            if search_results:
                relevant_schema, schema_context = format_schema_context_from_results(search_results)
        except Exception as search_err:
            logger.warning("Vector schema search encountered error: %s", search_err)

        retrieved_tables = list(relevant_schema.keys())
        logger.info(
            "--- [Node: intent] OUTPUT ---\n"
            "  Intent: %s\n"
            "  Entities: %s\n"
            "  Search Query: %s\n"
            "  Retrieved Tables: %s",
            intent_type,
            extracted_entities,
            search_query,
            retrieved_tables or "None",
        )

        return {
            "intent_type": intent_type,
            "extracted_entities": extracted_entities,
            "relevant_schema": relevant_schema,
            "schema_context": schema_context,
        }

    return intent_node
