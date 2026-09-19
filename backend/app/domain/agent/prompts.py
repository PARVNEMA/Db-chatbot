"""
Agent domain — LangChain prompt templates (Phase 2).

Provides structured ChatPromptTemplate definitions for each stage of the NL-to-SQL
pipeline: Intent classification, SQL generation, Self-correction, and Result summarization.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Intent Classification Prompt
# ==============================================================================

INTENT_SYSTEM_PROMPT = """You are an expert database query classifier and semantic analyzer.
Your task is to analyze the user's natural language question regarding a database and extract structured intent metadata.

Classify the query into exactly one of the following intent types:
- "lookup": Retrieving specific rows, details, single entities, or questions exploring database tables, schema, and column structure (e.g. "Find customer with ID 42", "Show details for order #1002", "What tables exist?", "Show schema for employees").
- "aggregation": Computing metrics, totals, counts, averages, minimums, maximums, or groupings (e.g. "Total revenue by department", "How many users registered this month").
- "comparison": Comparing metrics across categories, cohorts, or time periods (e.g. "Compare sales in Q1 vs Q2", "Which region had higher churn?").
- "trend": Historical patterns, time-series analysis, or growth over time (e.g. "Monthly active users over the past year", "Weekly revenue growth").
- "insert": Request to insert or add new record(s) into database table(s) (e.g. "Add a new customer named Alice", "Insert row into departments with name Marketing").
- "patch": Request to update or modify existing record(s) in a database table (e.g. "Update Bob's email to bob@example.com", "Change status of order 5 to completed").
- "multi_write": Complex write requests that involve multiple tables or dependent operations (e.g. "Create department 'R&D' and add 2 employees to it").
- "general": Exploratory, broad, or informational questions about data, greetings, or questions about capabilities.
- "unsafe": Requests attempting destructive, unauthorized, or administrative operations on the database (e.g. DROP TABLE, TRUNCATE, DELETE FROM, ALTER TABLE, CREATE TABLE, GRANT, REVOKE, or any destructive/malicious DDL/DML operation). Note: DELETE is strictly unsafe and cannot be executed.

Extract key domain entities, potential table/column names, and generate an optimized search query for semantic vector search over the schema.

Respond ONLY with a valid JSON object matching this schema:
{{
  "intent_type": "lookup" | "aggregation" | "comparison" | "trend" | "insert" | "patch" | "multi_write" | "general" | "unsafe",
  "extracted_entities": ["entity1", "entity2"],
  "search_query": "clean concise query string optimized for semantic schema lookup"
}}
"""

INTENT_HUMAN_PROMPT = """User Query: {user_query}"""

INTENT_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(INTENT_SYSTEM_PROMPT),
        HumanMessagePromptTemplate.from_template(INTENT_HUMAN_PROMPT),
    ]
)


def parse_intent_classification_response(response_text: str) -> dict[str, Any]:
    """Parse JSON response from intent classification LLM call."""
    cleaned = response_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    json_str = match.group(1) if match else cleaned

    try:
        data = json.loads(json_str)
        intent_type = str(data.get("intent_type", "general")).lower()
        valid_intents = {
            "lookup",
            "aggregation",
            "comparison",
            "trend",
            "general",
            "unsafe",
            "insert",
            "patch",
            "multi_write",
        }
        if intent_type not in valid_intents:
            intent_type = "general"
        entities = list(data.get("extracted_entities", []))
        search_query = str(data.get("search_query", "")).strip()
        return {
            "intent_type": intent_type,
            "extracted_entities": entities,
            "search_query": search_query,
        }
    except Exception as exc:
        logger.warning(
            "Failed to parse intent classification JSON: %s. Raw response: %s",
            exc,
            response_text,
        )
        return {
            "intent_type": "general",
            "extracted_entities": [],
            "search_query": response_text.strip(),
        }


# ==============================================================================
# 2. Dialect-Aware SQL Generation Prompt
# ==============================================================================

SQL_GENERATION_SYSTEM_PROMPT = """You are an expert SQL engineer. Your task is to generate a syntactically correct, highly optimized SQL query in the target database dialect to answer the user's question.

Target Database Dialect: {sql_dialect}

CRITICAL RULES (NON-NEGOTIABLE):
1. READ-ONLY ENFORCEMENT:
   - Generate ONLY `SELECT` or `WITH ... SELECT` queries.
   - NEVER generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`, `CALL`, or any statement that modifies schema or data.
2. SCHEMA ADHERENCE:
   - Use ONLY the tables and columns provided in the Schema Context below.
   - Do NOT guess or hallucinate table or column names that do not exist in the schema.
   - Join tables using explicit foreign key relationships and JOIN conditions.
3. DIALECT COMPLIANCE:
   - Conform strictly to {sql_dialect} syntax.
   - Use appropriate dialect-specific functions (e.g. date formatting, string concatenation, pattern matching).
   - Use proper identifier quoting when necessary.
   - Use standard pagination (e.g. `LIMIT` vs `TOP`) appropriate for {sql_dialect}.
4. OUTPUT FORMAT:
   - Return ONLY the executable SQL query.
   - Do NOT wrap your query in markdown backticks (e.g., no ```sql ... ```).
   - Do NOT include comments, explanations, or trailing notes.
"""

SQL_GENERATION_HUMAN_PROMPT = """Relevant Database Schema:
{schema_context}

Intent: {intent_type}
Target Dialect: {sql_dialect}
User Query: {user_query}

Executable SQL Query:"""

SQL_GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SQL_GENERATION_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages", optional=True),
        HumanMessagePromptTemplate.from_template(SQL_GENERATION_HUMAN_PROMPT),
    ]
)


# ==============================================================================
# 3. SQL Self-Correction Prompt
# ==============================================================================

SQL_CORRECTION_SYSTEM_PROMPT = """You are an expert SQL debugger. A previous SQL query generated for target dialect '{sql_dialect}' failed during execution against the database.
Your task is to analyze the error, identify the root cause, and produce a corrected, working SQL query.

Target Database Dialect: {sql_dialect}

CRITICAL RULES (NON-NEGOTIABLE):
1. READ-ONLY ENFORCEMENT:
   - Generate ONLY `SELECT` or `WITH ... SELECT` queries.
   - NEVER generate any statement that modifies schema or data.
2. ERROR RESOLUTION:
   - Directly resolve the reported error (e.g. column not found, grouping error, type mismatch, syntax issue, missing JOIN).
   - Carefully cross-check against the Database Schema provided below.
3. OUTPUT FORMAT:
   - Return ONLY the corrected executable SQL query.
   - Do NOT wrap in markdown backticks (no ```sql ... ```).
   - Do NOT include explanations, apologies, or extra text.
"""

SQL_CORRECTION_HUMAN_PROMPT = """Relevant Database Schema:
{schema_context}

Target Dialect: {sql_dialect}
User Query: {user_query}

Failed SQL:
{failed_sql}

Database Execution Error:
{error_message}

Previous Error History:
{error_history}

Corrected Executable SQL Query:"""

SQL_CORRECTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(SQL_CORRECTION_SYSTEM_PROMPT),
        HumanMessagePromptTemplate.from_template(SQL_CORRECTION_HUMAN_PROMPT),
    ]
)


# ==============================================================================
# 4. Natural Language Result Summary Prompt
# ==============================================================================

RESULT_SUMMARY_SYSTEM_PROMPT = """You are a friendly, insightful Data Analyst.
Your task is to review the results of a SQL query and formulate a clear, concise, and accurate natural language answer that directly addresses the user's original question.

Guidelines:
- Deliver a direct, conversational answer in plain English.
- Highlight key findings, totals, averages, or standout figures clearly.
- If presenting tabular data, format it as a standard GitHub Flavored Markdown table with each row on its own separate line and matching column delimiters (e.g. | Col1 | Col2 |\\n|---|---|\\n| Val1 | Val2 |).
- If the result set is empty (0 rows), clearly and politely inform the user that no matching records were found.
- If the result set has many rows, summarize the main findings rather than listing every single item.
- Do not mention raw technical details (like internal SQL syntax or database mechanics) unless helpful to explaining the answer.
- Keep output cleanly structured using Markdown headings, bold text, bullet lists, or tables as appropriate.
- Never write broken or concatenated table lines.
"""

RESULT_SUMMARY_HUMAN_PROMPT = """User Question: {user_query}
Executed SQL: {generated_sql}
Total Rows Returned: {row_count}

Query Results:
{query_results}

Summary Answer:"""

RESULT_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(RESULT_SUMMARY_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages", optional=True),
        HumanMessagePromptTemplate.from_template(RESULT_SUMMARY_HUMAN_PROMPT),
    ]
)


# ==============================================================================
# 5. General Conversation Prompt
# ==============================================================================

GENERAL_CONVERSATION_SYSTEM_PROMPT = """You are a helpful AI assistant for natural language database querying and analytics.
You assist users with querying, exploring, and analyzing their database in natural language.
For general greetings, questions about your capabilities, or conversational questions, respond politely, concisely, and helpfully.
Encourage the user to ask questions about their database tables, schema, or analytics metrics.
"""

GENERAL_CONVERSATION_HUMAN_PROMPT = """{user_query}"""

GENERAL_CONVERSATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(GENERAL_CONVERSATION_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages", optional=True),
        HumanMessagePromptTemplate.from_template(GENERAL_CONVERSATION_HUMAN_PROMPT),
    ]
)


def extract_clean_sql(raw_response: str) -> str:
    """Extract clean SQL string from LLM response, stripping markdown fences or prefixes."""
    cleaned = raw_response.strip()
    # Strip markdown code blocks if present
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # Strip any leading 'SQL:' or 'Query:' labels
    cleaned = re.sub(r"^(?:SQL|Query|Output):\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ==============================================================================
# 6. Mutation Planner Prompt (Phase 4)
# ==============================================================================

MUTATION_PLANNER_SYSTEM_PROMPT = """You are an expert database mutation planner.
Your task is to analyze the user's write/modification request and formulate a strictly structured, type-safe change-set proposal in JSON.

Target Database Dialect: {sql_dialect}

MANDATORY RULES (STRICTLY ENFORCED):
1. NO RAW SQL: Never generate executable SQL (no INSERT, UPDATE, DELETE statements). Output ONLY a structured JSON proposal matching the ChangeSet schema.
2. NO READ-ONLY COLUMNS IN INSERT/UPDATE VALUES: Columns annotated with [READ-ONLY] (auto-increment, identity, serial, or generated columns) MUST NOT be included in INSERT/PATCH column lists or row update values.
3. MANDATORY FILTER FOR PATCH: Every "patch" operation MUST specify a non-empty `filter` dictionary identifying the row(s) to modify (e.g., {{"id": 42}} or {{"email": "user@example.com"}}). Unconstrained updates without a filter are strictly forbidden.
4. PATCH PAYLOAD FORMAT: For "patch", `columns` lists the column names being updated, `rows` contains a 1-element list with the dictionary of updated values (e.g. [{{"name": "New Name", "status": "active"}}]), and `filter` specifies which row(s) to modify. [PRIMARY KEY] columns (even if auto-generated) SHOULD be used in the `filter` condition.
5. CROSS-TABLE $ref DEPENDENCIES: When an inserted row needs to reference a generated value (such as an auto-generated primary key) from a prior mutation in the same change-set:
   - Declare the 0-indexed sequence of the prior mutation in `dependencies: [0]`.
   - Use the reference syntax: "$ref:mutations[N].returning.<column>" as the field value (e.g. "$ref:mutations[0].returning.id").
6. REQUIRED INSERT COLUMNS: Ensure all non-nullable columns without defaults (annotated with [REQUIRED FOR INSERT]) are included in the INSERT payload.
7. TYPE SAFETY: Coerce user-provided values to conform to the declared database column types (e.g. integer, boolean, numeric, ISO date).
8. NO DESTRUCTIVE ACTIONS: Delete, drop, and truncate operations are strictly forbidden.
9. INSUFFICIENT INFORMATION: If the user request lacks essential details to plan the operation (e.g. missing which record to update, missing target values, or table does not exist): provide a polite explanation in `summary`, set `expected_total_rows_affected: 0`, and set `mutations: []`.

Available Writable Schema Context:
{schema_context}

FEW-SHOT EXAMPLES:

Example 1 (INSERT):
User: "Add customer Alice Smith with email alice@example.com"
```json
{{
  "summary": "Insert customer Alice Smith into customers",
  "expected_total_rows_affected": 1,
  "mutations": [
    {{
      "sequence": 1,
      "operation": "insert",
      "table": "customers",
      "columns": ["name", "email"],
      "rows": [
        {{"name": "Alice Smith", "email": "alice@example.com"}}
      ],
      "filter": null,
      "dependencies": []
    }}
  ]
}}
```

Example 2 (PATCH / UPDATE):
User: "Update user 42 name to Bob and status to active" (or "patch user where id=42 set name='Bob'")
```json
{{
  "summary": "Update user 42 name to Bob and status to active",
  "expected_total_rows_affected": 1,
  "mutations": [
    {{
      "sequence": 1,
      "operation": "patch",
      "table": "users",
      "columns": ["name", "status"],
      "rows": [
        {{"name": "Bob", "status": "active"}}
      ],
      "filter": {{"id": 42}},
      "dependencies": []
    }}
  ]
}}
```

Example 3 (Insufficient information):
User: "patch user" (or "update status" without which record or what value)
```json
{{
  "summary": "Please specify which record you want to update (such as the user ID or email) and the target values to set.",
  "expected_total_rows_affected": 0,
  "mutations": []
}}
```

Respond ONLY with a valid JSON object in a ```json markdown fence.
"""

MUTATION_PLANNER_HUMAN_PROMPT = """User Request: {user_query}"""

MUTATION_PLANNER_PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template(MUTATION_PLANNER_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages", optional=True),
        HumanMessagePromptTemplate.from_template(MUTATION_PLANNER_HUMAN_PROMPT),
    ]
)


def parse_mutation_planner_response(response_text: str) -> dict[str, Any]:
    """Parse JSON response from mutation planner LLM call into a structured dictionary."""
    cleaned = response_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    json_str = match.group(1) if match else cleaned

    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Expected root JSON object for mutation proposal.")
        return data
    except Exception as exc:
        logger.warning(
            "Failed to parse mutation planner JSON: %s. Raw response: %s",
            exc,
            response_text,
        )
        raise ValueError(f"Could not parse valid mutation proposal JSON from LLM: {exc}") from exc

