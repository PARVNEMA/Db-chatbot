"""Unit tests for unsafe/destructive intent guardrail and refusal flow."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.agent.dependencies import GraphDependencies
from app.domain.agent.graph import build_agent_graph, route_after_intent
from app.domain.agent.guardrail import detect_unsafe_intent
from app.domain.agent.nodes.intent import create_intent_node
from app.domain.agent.prompts import parse_intent_classification_response
from app.domain.agent.sql_validator import validate_safe_write_sql
from app.domain.agent.state import AgentState

# ==============================================================================
# 1. Deterministic Guardrail Regex Tests
# ==============================================================================


@pytest.mark.parametrize(
    "query,expected_match",
    [
        ("DROP TABLE users", True),
        ("drop table if exists customers", True),
        ("Can you drop the database prod_db?", True),
        ("TRUNCATE table orders", True),
        ("TRUNCATE orders", True),
        ("truncate", True),
        ("DELETE FROM users WHERE id = 1", True),
        ("delete all records from logs", True),
        ("delete everything from customers", True),
        ("delete every row in payments", True),
        ("ALTER TABLE accounts ADD COLUMN balance INT", True),
        ("alter database test_db", True),
        ("INSERT INTO users (name) VALUES ('hacker')", True),
        ("UPDATE accounts SET balance = 0", True),
        ("CREATE TABLE backdoor (id int)", True),
        ("create database test", True),
        ("GRANT ALL PRIVILEGES ON DATABASE mydb TO hacker", True),
        ("revoke select on users from guest", True),
        ("EXEC sp_executesql N'SELECT 1'", True),
        ("SELECT * FROM users; DROP TABLE users", True),
        ("SELECT 1; TRUNCATE TABLE orders", True),
    ],
)
def test_detect_unsafe_intent_positives(query: str, expected_match: bool) -> None:
    """Test that dangerous and destructive statements are detected as unsafe."""
    result = detect_unsafe_intent(query)
    assert (result is not None) == expected_match


@pytest.mark.parametrize(
    "query",
    [
        ("How many users registered this month?"),
        ("Show me the top 10 customers by revenue"),
        ("What is the average order value?"),
        ("Compare sales in Q1 vs Q2"),
        ("List all columns in the orders table"),
        ("Show table schema for customers"),
        ("Hello, who are you?"),
        ("I dropped my coffee on the keyboard"),
        ("Can you tell me about the drop-down menu feature?"),
        (""),
        ("   "),
    ],
)
def test_detect_unsafe_intent_negatives(query: str) -> None:
    """Test that benign analytics questions and casual speech do not trigger false positives."""
    result = detect_unsafe_intent(query)
    assert result is None


# ==============================================================================
# 2. Prompt Parser Tests
# ==============================================================================


def test_parse_intent_classification_with_unsafe() -> None:
    """Test that parse_intent_classification_response accepts 'unsafe' as valid."""
    raw = '{"intent_type": "unsafe", "extracted_entities": ["users"], "search_query": "drop table"}'
    parsed = parse_intent_classification_response(raw)
    assert parsed["intent_type"] == "unsafe"
    assert parsed["extracted_entities"] == ["users"]


@pytest.mark.parametrize("write_intent", ["insert", "patch", "multi_write"])
def test_parse_intent_classification_with_write_intents(write_intent: str) -> None:
    """Test that parse_intent_classification_response accepts insert, patch, and multi_write."""
    raw = f'{{"intent_type": "{write_intent}", "extracted_entities": ["departments"], "search_query": "departments"}}'
    parsed = parse_intent_classification_response(raw)
    assert parsed["intent_type"] == write_intent


# ==============================================================================
# 3. Graph Routing Tests
# ==============================================================================


def test_route_after_intent_with_unsafe() -> None:
    """Test that route_after_intent routes 'unsafe' directly to 'unsafe_handler'."""
    state_unsafe: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "DROP TABLE users",
        "intent_type": "unsafe",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }
    assert route_after_intent(state_unsafe) == "unsafe_handler"


@pytest.mark.parametrize("write_intent", ["insert", "patch", "multi_write"])
def test_route_after_intent_with_write_intents(write_intent: str) -> None:
    """Test that route_after_intent routes write intents to 'mutation_planner'."""
    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "Add new department",
        "intent_type": write_intent,
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }
    assert route_after_intent(state) == "mutation_planner"



# ==============================================================================
# 4. Intent Node Pre-Classification Short-Circuit
# ==============================================================================


@pytest.mark.asyncio
async def test_intent_node_bypasses_llm_and_vector_search_on_unsafe() -> None:
    """Test that intent_node detects unsafe query upfront and skips both LLM and vector search."""
    mock_llm = MagicMock()
    mock_embedding = MagicMock()

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=MagicMock(),
        embedding_service=mock_embedding,
        connection_service=MagicMock(),
        project_service=MagicMock(),
        user_id=uuid.uuid4(),
        connection=MagicMock(dialect="postgresql"),
        llm=mock_llm,
    )

    intent_node = create_intent_node(mock_deps)

    state: AgentState = {
        "project_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "user_query": "DROP TABLE users;",
        "intent_type": "general",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    result = await intent_node(state)

    assert result["intent_type"] == "unsafe"
    assert result["relevant_schema"] == {}
    assert result["schema_context"] == ""
    # Verify LLM was NOT called
    mock_llm.ainvoke.assert_not_called()
    # Verify vector embedding search was NOT called
    mock_embedding.search_schema.assert_not_called()


# ==============================================================================
# 5. Full Graph Workflow Execution on Unsafe Query
# ==============================================================================


@pytest.mark.asyncio
async def test_full_graph_unsafe_query_workflow() -> None:
    """Test executing full graph on a destructive prompt returns refusal message without generating or executing SQL."""
    project_id = uuid.uuid4()
    session_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    mock_llm = MagicMock()
    mock_cm = MagicMock()

    mock_deps = GraphDependencies(
        db=AsyncMock(),
        connection_manager=mock_cm,
        embedding_service=MagicMock(),
        connection_service=MagicMock(),
        project_service=MagicMock(),
        user_id=uuid.uuid4(),
        connection=MagicMock(dialect="postgresql"),
        llm=mock_llm,
    )

    graph = build_agent_graph(mock_deps)

    initial_state: AgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "connection_id": connection_id,
        "user_query": "DROP TABLE users;",
        "intent_type": "general",
        "extracted_entities": [],
        "relevant_schema": {},
        "schema_context": "",
        "generated_sql": "",
        "sql_dialect": "postgresql",
        "execution_result": [],
        "execution_error": None,
        "retry_count": 0,
        "error_history": [],
        "nl_summary": "",
        "messages": [],
    }

    final_state = await graph.ainvoke(initial_state)

    # 1. Intent should be classified as unsafe
    assert final_state["intent_type"] == "unsafe"
    # 2. Refusal message returned
    assert "read-only" in final_state["nl_summary"].lower()
    assert "cannot execute" in final_state["nl_summary"].lower()
    # 3. No SQL generated or executed
    assert final_state["generated_sql"] == ""
    assert final_state["execution_result"] == []
    mock_cm.execute_safe.assert_not_called()


# ==============================================================================
# 5. Write Guardrail & Safe Write AST Tests (Phase 3)
# ==============================================================================


@pytest.mark.parametrize(
    "query,writes_enabled,expected_unsafe",
    [
        # When writes are disabled (default), insert and update are blocked
        ("INSERT INTO users (name) VALUES ('Alice')", False, True),
        ("UPDATE accounts SET balance = 100 WHERE id = 1", False, True),
        # When writes are enabled, insert and update pass the pre-classification guardrail
        ("INSERT INTO users (name) VALUES ('Alice')", True, False),
        ("UPDATE accounts SET balance = 100 WHERE id = 1", True, False),
        ("insert into orders (item, qty) values ('Widget', 5)", True, False),
        ("update customers set status = 'active' where id = 42", True, False),
        # Destructive commands are ALWAYS unsafe, even when writes_enabled=True
        ("DROP TABLE users", True, True),
        ("TRUNCATE TABLE logs", True, True),
        ("DELETE FROM customers WHERE id = 1", True, True),
        ("ALTER TABLE users ADD COLUMN phone VARCHAR(20)", True, True),
        ("CREATE TABLE backdoor (id int)", True, True),
        ("GRANT ALL PRIVILEGES ON DATABASE mydb TO hacker", True, True),
        ("REVOKE SELECT ON users FROM guest", True, True),
        ("EXEC sp_executesql N'SELECT 1'", True, True),
        # Multi-statement attacks are ALWAYS unsafe, even when writes_enabled=True
        ("SELECT 1; DROP TABLE users", True, True),
        ("INSERT INTO users (name) VALUES ('Alice'); DROP TABLE users", True, True),
    ],
)
def test_detect_unsafe_intent_with_writes_enabled(
    query: str,
    writes_enabled: bool,
    expected_unsafe: bool,
) -> None:
    """Test guardrail behavior when writes_enabled is toggled."""
    match = detect_unsafe_intent(query, writes_enabled=writes_enabled)
    assert (match is not None) == expected_unsafe


def test_validate_safe_write_sql_when_writes_disabled() -> None:
    """Validate that writes are rejected when writes_enabled=False."""
    with pytest.raises(ValueError, match="Write operations are disabled"):
        validate_safe_write_sql(
            "INSERT INTO users (name) VALUES ('Alice')",
            writes_enabled=False,
        )


def test_validate_safe_write_sql_valid_insert() -> None:
    """Validate that safe INSERT statement passes validation when writes_enabled=True."""
    validate_safe_write_sql(
        "INSERT INTO users (name) VALUES ('Alice')",
        writes_enabled=True,
    )


def test_validate_safe_write_sql_valid_update_with_where() -> None:
    """Validate that UPDATE with WHERE clause passes validation."""
    validate_safe_write_sql(
        "UPDATE users SET name = 'Bob' WHERE id = 1",
        writes_enabled=True,
    )


def test_validate_safe_write_sql_rejects_unconstrained_update() -> None:
    """Validate that UPDATE without WHERE clause is rejected."""
    with pytest.raises(ValueError, match="WHERE clause"):
        validate_safe_write_sql(
            "UPDATE users SET name = 'Bob'",
            writes_enabled=True,
        )


def test_validate_safe_write_sql_rejects_destructive_dml() -> None:
    """Validate that DELETE and DROP are rejected even when writes_enabled=True."""
    with pytest.raises(ValueError, match="Forbidden"):
        validate_safe_write_sql(
            "DELETE FROM users WHERE id = 1",
            writes_enabled=True,
        )

    with pytest.raises(ValueError, match="Forbidden"):
        validate_safe_write_sql(
            "DROP TABLE users",
            writes_enabled=True,
        )


def test_validate_safe_write_sql_rejects_multistatement() -> None:
    """Validate that chained statements are rejected."""
    with pytest.raises(ValueError, match="Multi-statement execution rejected"):
        validate_safe_write_sql(
            "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')",
            writes_enabled=True,
        )

