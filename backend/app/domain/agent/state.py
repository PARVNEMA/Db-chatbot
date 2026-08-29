"""
Agent domain — LangGraph graph state definition (ADR-0003).

`AgentState` is the typed state dict passed between graph nodes.
All fields are scoped by project_id, session_id, and connection_id.
"""

from typing import Annotated, Any
from uuid import UUID

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State propagated through the LangGraph agent pipeline."""

    # --- Tenant & Connection scope ---
    project_id: UUID
    session_id: UUID
    connection_id: UUID

    # --- Input ---
    user_query: str

    # --- Intent node output ---
    intent_type: str  # "lookup" | "aggregation" | "comparison" | "trend" | "general"
    extracted_entities: list[str]
    relevant_schema: dict[str, Any]  # Retrieved schema subset
    schema_context: str  # Formatted schema text prompt

    # --- SQL generation ---
    generated_sql: str
    sql_dialect: str

    # --- Execution ---
    execution_result: list[dict[str, Any]]
    execution_error: str | None

    # --- Self-correction ---
    retry_count: int  # Max retries: 3
    error_history: list[str]

    # --- Result formatter ---
    nl_summary: str

    # --- Multi-turn message history (LangGraph managed) ---
    messages: Annotated[list[Any], add_messages]

