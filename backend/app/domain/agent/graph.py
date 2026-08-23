"""
Agent domain — LangGraph graph definition (ADR-0003).

Wires together the node pipeline:
  Intent Node → SQL Generator → SQL Executor → Self-Correction → Result Formatter

SSE streaming is performed via FastAPI EventSourceResponse over this graph.
"""

# TODO: implement in Phase 3
# from langgraph.graph import StateGraph, END
# from app.domain.agent.state import AgentState
# from app.domain.agent.nodes.intent import intent_node
# from app.domain.agent.nodes.sql_generator import sql_generator_node
# from app.domain.agent.nodes.sql_executor import sql_executor_node
# from app.domain.agent.nodes.result_formatter import result_formatter_node
#
# def build_agent_graph():
#     graph = StateGraph(AgentState)
#     graph.add_node("intent", intent_node)
#     graph.add_node("sql_generator", sql_generator_node)
#     graph.add_node("sql_executor", sql_executor_node)
#     graph.add_node("result_formatter", result_formatter_node)
#     graph.set_entry_point("intent")
#     graph.add_edge("intent", "sql_generator")
#     graph.add_edge("sql_generator", "sql_executor")
#     graph.add_conditional_edges(...)  # self-correction loop
#     graph.add_edge("result_formatter", END)
#     return graph.compile(checkpointer=AsyncPostgresSaver(...))
