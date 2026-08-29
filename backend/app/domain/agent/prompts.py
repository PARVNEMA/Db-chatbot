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
- "lookup": Retrieving specific rows, details, or single entities (e.g. "Find customer with ID 42", "Show details for order #1002").
- "aggregation": Computing metrics, totals, counts, averages, minimums, maximums, or groupings (e.g. "Total revenue by department", "How many users registered this month").
- "comparison": Comparing metrics across categories, cohorts, or time periods (e.g. "Compare sales in Q1 vs Q2", "Which region had higher churn?").
- "trend": Historical patterns, time-series analysis, or growth over time (e.g. "Monthly active users over the past year", "Weekly revenue growth").
- "general": Exploratory, broad, or informational questions about data.

Extract key domain entities, potential table/column names, and generate an optimized search query for semantic vector search over the schema.

Respond ONLY with a valid JSON object matching this schema:
{{
  "intent_type": "lookup" | "aggregation" | "comparison" | "trend" | "general",
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
        if intent_type not in {"lookup", "aggregation", "comparison", "trend", "general"}:
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
- If the result set is empty (0 rows), clearly and politely inform the user that no matching records were found.
- If the result set has many rows, summarize the main findings rather than listing every single item.
- Do not mention raw technical details (like internal SQL syntax or database mechanics) unless helpful to explaining the answer.
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
        HumanMessagePromptTemplate.from_template(RESULT_SUMMARY_HUMAN_PROMPT),
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
