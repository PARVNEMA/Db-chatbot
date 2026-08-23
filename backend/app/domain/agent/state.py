"""
Agent domain — LangGraph graph state definition (ADR-0003).

`AgentState` is the typed state dict passed between graph nodes.
All fields are scoped by project_id and session_id.
"""

from typing import Annotated, Any
from uuid import UUID

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State propagated through the LangGraph agent pipeline."""

    # --- Tenant scope ---
    project_id: UUID
    session_id: UUID

    # --- Input ---
    user_query: str

    # --- Intent node output ---
    intent_type: str  # "lookup" | "aggregation" | "comparison" | "trend"
    extracted_entities: list[str]
    relevant_schema: dict[str, Any]  # Retrieved schema subset

    # --- SQL generation ---
    generated_sql: str
    sql_dialect: str

    # --- Execution ---
    execution_result: list[dict[str, Any]]
    execution_error: str | None

    # --- Self-correction ---
    retry_count: int  # Max retries: 3

    # --- Result formatter ---
    nl_summary: str

    # --- Multi-turn message history (LangGraph managed) ---
    messages: Annotated[list[Any], add_messages]
