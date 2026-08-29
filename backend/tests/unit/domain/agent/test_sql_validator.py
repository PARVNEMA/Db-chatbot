"""
Unit tests for SQL AST validator and Read-Only Guardrails (Phase 3).
"""

import pytest

from app.domain.agent.sql_validator import (
    extract_tables_from_sql,
    sanitize_sql,
    validate_read_only,
)


def test_sanitize_sql() -> None:
    """Test comment stripping and whitespace cleanup."""
    raw = """
    -- Single line comment
    SELECT id, name /* inline comment */
    FROM users
    WHERE active = true; -- trailing comment
    """
    sanitized = sanitize_sql(raw)
    assert "--" not in sanitized
    assert "/*" not in sanitized
    assert not sanitized.endswith(";")
    assert "SELECT id, name" in sanitized


def test_extract_tables_from_sql() -> None:
    """Test extracting table names from SELECT queries."""
    sql = """
    SELECT u.id, u.name, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE o.created_at >= '2026-01-01'
    """
    tables = extract_tables_from_sql(sql)
    assert "users" in tables
    assert "orders" in tables


def test_validate_read_only_valid_queries() -> None:
    """Test valid SELECT and CTE queries pass validation."""
    valid_queries = [
        "SELECT * FROM customers;",
        "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o ON c.id = o.customer_id GROUP BY c.name;",
        "WITH recent_orders AS (SELECT * FROM orders WHERE created_at > '2026-01-01') SELECT * FROM recent_orders;",
        "SELECT id, price FROM products WHERE price > 100 ORDER BY price DESC LIMIT 10;",
        "SELECT 1 UNION SELECT 2;",
    ]
    for q in valid_queries:
        validate_read_only(q)  # Should not raise


def test_validate_read_only_rejects_empty_query() -> None:
    """Test empty query raises ValueError."""
    with pytest.raises(ValueError, match="SQL query is empty"):
        validate_read_only("   ")


@pytest.mark.parametrize(
    "query, forbidden_word",
    [
        ("INSERT INTO users (name) VALUES ('Hacker')", "insert"),
        ("UPDATE users SET name = 'Admin' WHERE id = 1", "update"),
        ("DELETE FROM orders WHERE id = 42", "delete"),
        ("DROP TABLE customers CASCADE", "drop"),
        ("TRUNCATE TABLE logs", "truncate"),
        ("ALTER TABLE users ADD COLUMN password_hash TEXT", "alter"),
        ("CREATE TABLE evil (id INT)", "create"),
        ("GRANT ALL PRIVILEGES ON database TO evil", "grant"),
        ("REVOKE ALL PRIVILEGES ON database FROM user", "revoke"),
    ],
)
def test_validate_read_only_rejects_ddl_and_dml(query: str, forbidden_word: str) -> None:
    """Test DDL and DML operations are blocked."""
    with pytest.raises(ValueError):
        validate_read_only(query)


def test_validate_read_only_rejects_semicolon_chaining() -> None:
    """Test multi-statement injection is blocked."""
    evil_query = "SELECT * FROM users; DROP TABLE products;"
    with pytest.raises(ValueError, match="Multi-statement execution rejected|Forbidden keyword"):
        validate_read_only(evil_query)


def test_validate_read_only_rejects_cte_with_dml() -> None:
    """Test CTE containing DML is blocked."""
    evil_cte = "WITH deleted_rows AS (DELETE FROM orders RETURNING *) SELECT * FROM deleted_rows;"
    with pytest.raises(ValueError):
        validate_read_only(evil_cte)
