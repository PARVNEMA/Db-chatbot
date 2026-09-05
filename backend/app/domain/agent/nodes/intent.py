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
from app.domain.schema_introspection.schemas import TableDetailResponse

logger = logging.getLogger(__name__)


def format_schema_context_from_table_details(
    tables: list[TableDetailResponse],
) -> tuple[dict[str, Any], str]:
    """Format full TableDetailResponse objects into structured dict and prompt string.

    The output string includes:
    - A per-table column listing with PK/FK annotations for all columns.
    - A dedicated "Relationships" section summarising all FK join paths so the
      LLM can construct correct JOINs without guessing.
    """
    if not tables:
        return {}, ""

    tables_map: dict[str, list[dict[str, Any]]] = {}
    schema_lines: list[str] = []
    join_hints: list[str] = []

    for table in sorted(tables, key=lambda t: t.table_name):
        col_list: list[dict[str, Any]] = []
        schema_lines.append(f"Table: {table.table_name}")
        schema_lines.append("Columns:")

        for col in sorted(table.columns, key=lambda c: c.ordinal_position):
            col_info = {
                "name": col.column_name,
                "type": col.data_type,
                "is_primary_key": col.is_primary_key,
                "is_foreign_key": col.is_foreign_key,
                "fk_target_table": col.fk_target_table,
                "fk_target_column": col.fk_target_column,
            }
            col_list.append(col_info)

            flags: list[str] = []
            if col.is_primary_key:
                flags.append("PRIMARY KEY")
            if col.is_foreign_key and col.fk_target_table:
                target_col = col.fk_target_column or "id"
                fk_ref = f"REFERENCES {col.fk_target_table}.{target_col}"
                flags.append(fk_ref)
                join_hints.append(
                    f"  {table.table_name}.{col.column_name} -> {col.fk_target_table}.{target_col}"
                    f"  (JOIN {col.fk_target_table} ON {table.table_name}.{col.column_name} = {col.fk_target_table}.{target_col})"
                )

            flag_str = f" [{' | '.join(flags)}]" if flags else ""
            schema_lines.append(f"  - {col.column_name} ({col.data_type}){flag_str}")

        tables_map[table.table_name] = col_list
        schema_lines.append("")

    if join_hints:
        unique_join_hints = list(dict.fromkeys(join_hints))
        schema_lines.append("Relationships (use these JOIN paths to fetch human-readable fields):")
        schema_lines.extend(unique_join_hints)
        schema_lines.append("")

    return tables_map, "\n".join(schema_lines).strip()


def _match_entity_tables(
    entities: list[str] | None,
    tables_by_name: dict[str, TableDetailResponse],
) -> set[str]:
    """Find tables matching extracted entities using direct and plural/singular matching."""
    matched: set[str] = set()
    if not entities:
        return matched

    for entity in entities:
        clean = entity.strip().lower()
        if not clean:
            continue
        if clean in tables_by_name:
            matched.add(clean)
        elif clean.rstrip("s") in tables_by_name:
            matched.add(clean.rstrip("s"))
        elif f"{clean}s" in tables_by_name:
            matched.add(f"{clean}s")
    return matched


def _expand_outward_fks(
    target_names: set[str],
    tables_by_name: dict[str, TableDetailResponse],
) -> set[str]:
    """Retrieve parent tables referenced via foreign keys from target tables."""
    outward: set[str] = set()
    for name in target_names:
        table_obj = tables_by_name.get(name)
        if not table_obj:
            continue
        for col in table_obj.columns:
            if col.is_foreign_key and col.fk_target_table:
                fk_target = col.fk_target_table.lower()
                if fk_target in tables_by_name:
                    outward.add(fk_target)
    return outward


def _find_junction_tables(
    target_names: set[str],
    tables_by_name: dict[str, TableDetailResponse],
) -> set[str]:
    """Detect unselected tables that act as junction tables between 2 or more target tables."""
    junctions: set[str] = set()
    for name, table in tables_by_name.items():
        if name in target_names:
            continue
        refs = {
            col.fk_target_table.lower()
            for col in table.columns
            if col.is_foreign_key and col.fk_target_table and col.fk_target_table.lower() in target_names
        }
        if len(refs) >= 2:
            junctions.add(name)
    return junctions


def expand_schema_tables(
    search_results: list[SchemaSearchResult],
    all_tables: list[TableDetailResponse],
    extracted_entities: list[str] | None = None,
) -> list[TableDetailResponse]:
    """Expand schema tables using vector search hits, FK relationships, and extracted entities.

    1. Identifies directly matched tables from vector search results.
    2. Incorporates tables matching extracted entities (with singular/plural matching).
    3. Traverses foreign keys (outward FK expansion) to include referenced parent tables
       (e.g., employee_projects -> employees, projects).
    4. Detects junction tables connecting any pair of included tables.
    """
    if not all_tables:
        return []

    tables_by_name: dict[str, TableDetailResponse] = {
        t.table_name.lower(): t for t in all_tables
    }

    # 1. Matched tables and direct FK targets from vector search
    target_table_names: set[str] = set()
    for res in search_results:
        t_name = res.table_name.lower()
        if t_name in tables_by_name:
            target_table_names.add(t_name)
        if res.is_foreign_key and res.fk_target_table:
            fk_target = res.fk_target_table.lower()
            if fk_target in tables_by_name:
                target_table_names.add(fk_target)

    # 2. Entity linking
    target_table_names |= _match_entity_tables(extracted_entities, tables_by_name)
    if not target_table_names:
        return []

    # 3. Outward FK expansion
    target_table_names |= _expand_outward_fks(target_table_names, tables_by_name)

    # 4. Junction table expansion
    target_table_names |= _find_junction_tables(target_table_names, tables_by_name)

    return [tables_by_name[name] for name in target_table_names if name in tables_by_name]


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

        # 3. Retrieve schema context via vector similarity search and FK graph expansion
        relevant_schema: dict[str, Any] = {}
        schema_context: str = ""

        search_results: list[SchemaSearchResult] = []
        try:
            search_results = await deps.embedding_service.search_schema(
                project_id=project_id,
                user_id=deps.user_id,
                query=search_query,
            )
        except Exception as search_err:
            logger.warning("Vector schema search encountered error: %s", search_err)

        # 4. Expand tables using FK relationships from the schema introspection service
        if deps.schema_service is not None:
            try:
                all_tables = await deps.schema_service.list_tables(
                    project_id=project_id,
                    user_id=deps.user_id,
                )
                expanded_tables = expand_schema_tables(
                    search_results=search_results,
                    all_tables=all_tables,
                    extracted_entities=extracted_entities,
                )
                if expanded_tables:
                    relevant_schema, schema_context = format_schema_context_from_table_details(expanded_tables)
            except Exception as exp_err:
                logger.warning("Schema table expansion encountered error: %s; falling back.", exp_err)

        # Fallback to direct search results if expansion did not produce a schema context
        # if not relevant_schema and search_results:
        #     relevant_schema, schema_context = format_schema_context_from_results(search_results)

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
