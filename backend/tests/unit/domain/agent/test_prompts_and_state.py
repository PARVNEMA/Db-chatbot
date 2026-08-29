"""
Unit tests for Agent domain prompts and state definitions (Phases 1 & 2).
"""

import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.agent.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    RESULT_SUMMARY_PROMPT,
    SQL_CORRECTION_PROMPT,
    SQL_GENERATION_PROMPT,
    extract_clean_sql,
    parse_intent_classification_response,
)
from app.domain.agent.state import AgentState


def test_agent_state_keys() -> None:
    """Verify that AgentState has all required keys."""
    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "How many users signed up last week?",
        "intent_type": "aggregation",
        "extracted_entities": ["users"],
        "relevant_schema": {"users": ["id", "created_at"]},
        "schema_context": "Table: users (id, created_at)",
        "generated_sql": "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '7 days';",
        "sql_dialect": "postgresql",
        "execution_result": [{"count": 42}],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "There were 42 user signups last week.",
        "messages": [],
    }

    assert state["intent_type"] == "aggregation"
    assert state["retry_count"] == 0
    assert len(state["execution_result"]) == 1


def test_parse_intent_classification_response_valid_json() -> None:
    """Test parsing clean JSON intent response."""
    raw = '{"intent_type": "trend", "extracted_entities": ["orders", "revenue"], "search_query": "monthly revenue"}'
    parsed = parse_intent_classification_response(raw)
    assert parsed["intent_type"] == "trend"
    assert parsed["extracted_entities"] == ["orders", "revenue"]
    assert parsed["search_query"] == "monthly revenue"


def test_parse_intent_classification_response_markdown_fenced() -> None:
    """Test parsing markdown wrapped JSON intent response."""
    raw = """```json
    {
      "intent_type": "aggregation",
      "extracted_entities": ["customers"],
      "search_query": "customer count"
    }
    ```"""
    parsed = parse_intent_classification_response(raw)
    assert parsed["intent_type"] == "aggregation"
    assert parsed["extracted_entities"] == ["customers"]


def test_parse_intent_classification_response_fallback() -> None:
    """Test fallback when response is malformed."""
    raw = "I think the intent is to lookup a user."
    parsed = parse_intent_classification_response(raw)
    assert parsed["intent_type"] == "general"
    assert parsed["extracted_entities"] == []
    assert parsed["search_query"] == raw


def test_extract_clean_sql() -> None:
    """Test extracting clean SQL from various markdown formats."""
    raw1 = "```sql\nSELECT id, name FROM users LIMIT 10;\n```"
    assert extract_clean_sql(raw1) == "SELECT id, name FROM users LIMIT 10;"

    raw2 = "SQL: SELECT * FROM products;"
    assert extract_clean_sql(raw2) == "SELECT * FROM products;"

    raw3 = "SELECT COUNT(*) FROM orders;"
    assert extract_clean_sql(raw3) == "SELECT COUNT(*) FROM orders;"


def test_prompt_templates_formatting() -> None:
    """Test that all ChatPromptTemplates format properly with variables."""
    # 1. Intent prompt
    intent_messages = INTENT_CLASSIFICATION_PROMPT.format_messages(
        user_query="Show top 5 products by sales"
    )
    assert len(intent_messages) == 2
    assert isinstance(intent_messages[0], SystemMessage)
    assert isinstance(intent_messages[1], HumanMessage)
    assert "Show top 5 products by sales" in intent_messages[1].content

    # 2. SQL Gen prompt
    sql_gen_messages = SQL_GENERATION_PROMPT.format_messages(
        sql_dialect="postgresql",
        schema_context="Table: products (id, name, price)",
        intent_type="ranking",
        user_query="Top products",
        messages=[],
    )
    assert len(sql_gen_messages) >= 2
    assert "postgresql" in str(sql_gen_messages[0].content)

    # 3. SQL Correction prompt
    sql_corr_messages = SQL_CORRECTION_PROMPT.format_messages(
        sql_dialect="postgresql",
        schema_context="Table: products (id, name)",
        user_query="Top products",
        failed_sql="SELECT names FROM products",
        error_message="column 'names' does not exist",
        error_history="Attempt 1: column 'names' does not exist",
    )
    assert len(sql_corr_messages) == 2
    assert "column 'names' does not exist" in str(sql_corr_messages[1].content)

    # 4. Result Summary prompt
    summary_messages = RESULT_SUMMARY_PROMPT.format_messages(
        user_query="How many orders today?",
        generated_sql="SELECT COUNT(*) FROM orders",
        row_count=1,
        query_results="[{'count': 15}]",
    )
    assert len(summary_messages) == 2
    assert "{'count': 15}" in str(summary_messages[1].content)
