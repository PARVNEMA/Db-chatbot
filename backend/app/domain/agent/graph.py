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
from app.domain.agent.nodes.missing_field_collector import create_missing_field_collector_node
from app.domain.agent.nodes.mutation_executor import create_mutation_executor_node
from app.domain.agent.nodes.mutation_planner import create_mutation_planner_node
from app.domain.agent.nodes.mutation_previewer import create_mutation_previewer_node
from app.domain.agent.nodes.mutation_result_formatter import create_mutation_result_formatter_node
from app.domain.agent.nodes.mutation_validator import create_mutation_validator_node
from app.domain.agent.nodes.result_formatter import create_result_formatter_node
from app.domain.agent.nodes.sql_executor import create_sql_executor_node
from app.domain.agent.nodes.sql_generator import create_sql_generator_node
from app.domain.agent.nodes.unsafe_handler import create_unsafe_handler_node
from app.domain.agent.state import AgentState

logger = logging.getLogger(__name__)

# Maximum retry attempts before giving up in the self-correction loop
MAX_RETRIES: int = 3


def route_after_intent(state: AgentState) -> str:
    """Route after intent: direct unsafe intent to unsafe_handler, write intents to mutation_planner, general conversation to general_chat, or proceed to sql_generator."""
    intent_type = state.get("intent_type", "general")
    if intent_type == "unsafe":
        next_node = "unsafe_handler"
    elif intent_type == "general":
        next_node = "general_chat"
    elif intent_type in ("insert", "patch", "multi_write"):
        next_node = "mutation_planner"
    else:
        next_node = "sql_generator"

    logger.info("--- [Graph Router] intent -> %s (intent_type=%s) ---", next_node, intent_type)
    return next_node


def route_after_mutation_planner(state: AgentState) -> str:
    """Route after mutation planner: inspect missing fields if proposal was generated, else format result."""
    status = state.get("mutation_status")
    if status == "planned":
        next_node = "missing_field_collector"
    else:
        next_node = "mutation_result_formatter"

    logger.info("--- [Graph Router] mutation_planner -> %s (status=%s) ---", next_node, status)
    return next_node


def route_after_missing_fields(state: AgentState) -> str:
    """Route after missing field collector: validate if all fields present, else prompt user for missing fields."""
    status = state.get("mutation_status")
    if status == "input_complete":
        next_node = "mutation_validator"
    else:
        next_node = "mutation_result_formatter"

    logger.info("--- [Graph Router] missing_field_collector -> %s (status=%s) ---", next_node, status)
    return next_node


def route_after_mutation_validation(state: AgentState) -> str:
    """Route after mutation validator: preview candidate rows if validated, else format error."""
    status = state.get("mutation_status")
    if status == "validated":
        next_node = "mutation_previewer"
    else:
        next_node = "mutation_result_formatter"

    logger.info("--- [Graph Router] mutation_validator -> %s (status=%s) ---", next_node, status)
    return next_node


def route_after_execution(state: AgentState) -> str:
    """Route state after execution: format results on success, retry up to 3 times, or terminate."""
    error = state.get("execution_error")
    retry_count = state.get("retry_count", 0)

    if error is None:
        logger.info("--- [Graph Router] sql_executor -> result_formatter (execution successful) ---")
        return "result_formatter"

    if retry_count < MAX_RETRIES:
        logger.info(
            "--- [Graph Router] sql_executor -> sql_generator (Self-correction retry %d/%d, error: %s) ---",
            retry_count,
            MAX_RETRIES,
            error,
        )
        return "sql_generator"

    logger.warning(
        "--- [Graph Router] sql_executor -> error_terminal (Max retries %d reached, error: %s) ---",
        MAX_RETRIES,
        error,
    )
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
    workflow.add_node("mutation_planner", create_mutation_planner_node(deps))
    workflow.add_node("missing_field_collector", create_missing_field_collector_node(deps))
    workflow.add_node("mutation_validator", create_mutation_validator_node(deps))
    workflow.add_node("mutation_previewer", create_mutation_previewer_node(deps))
    workflow.add_node("mutation_executor", create_mutation_executor_node(deps))
    workflow.add_node("mutation_result_formatter", create_mutation_result_formatter_node(deps))

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
            "mutation_planner": "mutation_planner",
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

    # 5. Write pipeline edges (Phase 5 HITL Flow)
    workflow.add_conditional_edges(
        "mutation_planner",
        route_after_mutation_planner,
        {
            "missing_field_collector": "missing_field_collector",
            "mutation_result_formatter": "mutation_result_formatter",
        },
    )
    # goes to result formatter if error needs to sent to the user
    workflow.add_conditional_edges(
        "missing_field_collector",
        route_after_missing_fields,
        {
            "mutation_validator": "mutation_validator",
            "mutation_result_formatter": "mutation_result_formatter",
        },
    )

    workflow.add_conditional_edges(
        "mutation_validator",
        route_after_mutation_validation,
        {
            "mutation_previewer": "mutation_previewer",
            "mutation_result_formatter": "mutation_result_formatter",
        },
    )

    workflow.add_edge("mutation_previewer", "mutation_result_formatter")

    # 6. Terminal edges
    workflow.add_edge("unsafe_handler", END)
    workflow.add_edge("general_chat", END)
    workflow.add_edge("result_formatter", END)
    workflow.add_edge("error_terminal", END)
    workflow.add_edge("mutation_result_formatter", END)

    logger.info("Compiled LangGraph agent workflow graph successfully.")
    return workflow.compile(checkpointer=checkpointer)
