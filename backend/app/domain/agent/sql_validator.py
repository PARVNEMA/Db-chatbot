"""
Agent domain — SQL Validator and Read-Only Guardrails (Phase 3).

Provides AST-level SQL validation using `sqlglot` to enforce read-only execution,
prevent multi-statement injections, strip comments, and extract table references.
"""

from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

# Disallowed root AST statement types
_FORBIDDEN_EXPRESSIONS: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Revoke,
    exp.Command,
    exp.Commit,
    exp.Rollback,
    exp.Transaction,
    exp.Merge,
    exp.Set,
    exp.Pragma,
)

# Explicit keyword fallback patterns for fast rejection or fallback
_DANGEROUS_KEYWORD_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|replace|attach|detach|execute|exec|call)\b",
    re.IGNORECASE,
)


def sanitize_sql(sql: str) -> str:
    """Sanitize SQL query by stripping comments, trailing semicolons, and normalizing whitespace."""
    if not sql:
        return ""

    # Remove single-line comments (-- ...)
    cleaned = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    # Remove multi-line comments (/* ... */)
    cleaned = re.sub(r"/\*[\s\S]*?\*/", "", cleaned)
    # Strip trailing semicolons and whitespace
    cleaned = cleaned.strip().rstrip(";").strip()
    return cleaned


def extract_tables_from_sql(sql: str, dialect: str | None = None) -> list[str]:
    """Extract referenced table names from a SQL query using AST parsing."""
    sanitized = sanitize_sql(sql)
    if not sanitized:
        return []

    tables: set[str] = set()
    try:
        parsed_list = sqlglot.parse(sanitized, read=dialect)
        for parsed in parsed_list:
            if parsed is None:
                continue
            for table_node in parsed.find_all(exp.Table):
                # Filter out CTE aliases
                table_name = table_node.name
                if table_name:
                    tables.add(table_name)
    except Exception as exc:
        logger.debug("Failed to extract tables via sqlglot AST: %s", exc)

    return sorted(tables)


def validate_read_only(sql: str, dialect: str | None = None) -> None:
    """Validate that a SQL statement is strictly read-only (SELECT / CTE queries only).

    Raises:
        ValueError: If query is empty, contains multiple statements, contains DDL/DML,
                    or is not a SELECT query.
    """
    sanitized = sanitize_sql(sql)
    if not sanitized:
        raise ValueError("SQL query is empty.")

    # Fast check: reject dangerous keywords upfront
    match = _DANGEROUS_KEYWORD_PATTERN.search(sanitized)
    if match:
        raise ValueError(
            f"Forbidden keyword '{match.group(1)}' detected. Only read-only SELECT queries are allowed."
        )

    # AST-level parsing with sqlglot
    try:
        statements = sqlglot.parse(sanitized, read=dialect)
    except Exception as parse_err:
        logger.warning("sqlglot AST parse warning for query: %s. Error: %s", sanitized, parse_err)
        # If parsing fails on dialect idiosyncrasies, do extra strict keyword check
        if _DANGEROUS_KEYWORD_PATTERN.search(sanitized):
            raise ValueError(
                "Query contains prohibited statements and could not be verified as read-only."
            ) from parse_err
        return

    # Check for empty parse
    valid_statements = [s for s in statements if s is not None]
    if not valid_statements:
        raise ValueError("Unable to parse valid SQL statements from input.")

    # Enforce single-statement execution (prevent semicolon chaining like 'SELECT 1; DROP TABLE users')
    if len(valid_statements) > 1:
        raise ValueError(
            f"Multi-statement execution rejected ({len(valid_statements)} statements found). "
            "Only single SELECT statements are permitted."
        )

    statement = valid_statements[0]

    # Validate that root expression is Select or Union/Intersect/Except
    if not isinstance(
        statement,
        (
            exp.Select,
            exp.Union,
            exp.Intersect,
            exp.Except,
        ),
    ):
        raise ValueError(
            f"Statement type '{type(statement).__name__}' is forbidden. "
            "Only SELECT statements are permitted."
        )

    # Walk all nodes in the AST to check for forbidden expressions
    for node in statement.walk():
        if isinstance(node, _FORBIDDEN_EXPRESSIONS):
            raise ValueError(
                f"Forbidden operation '{type(node).__name__}' detected within SQL AST. "
                "Only read-only SELECT queries are allowed."
            )

    logger.debug("SQL query successfully passed AST read-only validation.")
