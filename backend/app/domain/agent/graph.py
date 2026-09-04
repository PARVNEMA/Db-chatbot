"""
Agent domain — LangGraph graph definition (ADR-0003).

Wires together the complete NL-to-SQL agent pipeline:
  START → Intent Node → [Conditional Router]
                           ├── intent == "general" → General Chat Node → END
                           └── intent != "general" → SQL Generator → SQL Executor → [Conditional Router]
                                                                                      ├── success → Result Formatter → END
                                                                                      ├── error & retries < 3 → SQL Generator (Loop)
                                                                                      └── error & retries >= 3 → Error Terminal → END

Includes bounded self-correction loop (max 3 retries) and optional PostgreSQL checkpointer
for multi-turn state persistence.
"""

from __future__ import annotations

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.nodes.error_terminal import error_terminal_node
from app.domain.agent.nodes.general_chat import create_general_chat_node
from app.domain.agent.nodes.intent import create_intent_node
from app.domain.agent.nodes.result_formatter import create_result_formatter_node
from app.domain.agent.nodes.sql_executor import create_sql_executor_node
from app.domain.agent.nodes.sql_generator import create_sql_generator_node
from app.domain.agent.nodes.unsafe_handler import create_unsafe_handler_node
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)

# Maximum retry attempts before giving up in the self-correction loop
MAX_RETRIES: int = 3


def route_after_intent(state: AgentState) -> str:
    """Route after intent: direct unsafe intent to unsafe_handler, general conversation to general_chat, or proceed to sql_generator."""
    intent_type = state.get("intent_type", "general")
    if intent_type == "unsafe":
        logger.warning("Routing destructive/guardrail-breaking query to unsafe_handler node.")
        return "unsafe_handler"
    if intent_type == "general":
        logger.info("Routing general conversation query directly to general_chat node.")
        return "general_chat"
    return "sql_generator"


def route_after_execution(state: AgentState) -> str:
    """Route state after execution: format results on success, retry up to 3 times, or terminate."""
    error = state.get("execution_error")
    retry_count = state.get("retry_count", 0)

    if error is None:
        return "result_formatter"

    if retry_count < MAX_RETRIES:
        logger.info(
            "Routing to sql_generator for self-correction attempt %d/%d",
            retry_count + 1,
            MAX_RETRIES,
        )
        return "sql_generator"

    logger.warning("Max retries (%d) reached. Routing to error_terminal.", MAX_RETRIES)
    return "error_terminal"


def build_agent_graph(
    deps: GraphDependencies,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Construct and compile the LangGraph agent state graph.

    Args:
        deps: Resolved runtime dependencies container.
        checkpointer: Optional LangGraph checkpointer for persisting multi-turn conversation state.

    Returns:
        CompiledStateGraph instance ready for invocation or streaming.
    """
    workflow = StateGraph(AgentState)

    # 1. Register nodes
    workflow.add_node("intent", create_intent_node(deps))
    workflow.add_node("unsafe_handler", create_unsafe_handler_node())
    workflow.add_node("general_chat", create_general_chat_node(deps))
    workflow.add_node("sql_generator", create_sql_generator_node(deps))
    workflow.add_node("sql_executor", create_sql_executor_node(deps))
    workflow.add_node("result_formatter", create_result_formatter_node(deps))
    workflow.add_node("error_terminal", error_terminal_node)

    # 2. Add edges
    workflow.add_edge(START, "intent")

    # 3. Add conditional router after intent classification
    workflow.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "unsafe_handler": "unsafe_handler",
            "general_chat": "general_chat",
            "sql_generator": "sql_generator",
        },
    )

    workflow.add_edge("sql_generator", "sql_executor")

    # 4. Add conditional router after execution (Self-correction loop)
    workflow.add_conditional_edges(
        "sql_executor",
        route_after_execution,
        {
            "result_formatter": "result_formatter",
            "sql_generator": "sql_generator",
            "error_terminal": "error_terminal",
        },
    )

    # 5. Terminal edges
    workflow.add_edge("unsafe_handler", END)
    workflow.add_edge("general_chat", END)
    workflow.add_edge("result_formatter", END)
    workflow.add_edge("error_terminal", END)

    logger.info("Compiled LangGraph agent workflow graph successfully.")
    return workflow.compile(checkpointer=checkpointer)
