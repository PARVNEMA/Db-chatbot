# Domain Glossary (CONTEXT.md)

This document defines the canonical domain terminology for the **Natural Language Database Querying Platform**. Implementation details must adhere to these domain concepts.

---

## Core Entities & Boundaries

### Project
The root multi-tenant isolation boundary. Every Database Connection, Schema Cache, Semantic Layer metadata, Vector Store namespace, and Chat Session strictly belongs to exactly one `Project`.

### Database Connection
A configured connection target containing encrypted credentials, database dialect (e.g., PostgreSQL, MySQL, Snowflake, SQL Server), host details, and pooled execution parameters. Read-only guardrails are enforced at the connection execution level.

### Schema Introspection
The automated process of querying target database system catalogs (`information_schema` / dialect reflection) to extract tables, columns, primary keys, foreign keys, and data types into a structured, cached representation.

### Semantic Layer (Metadata)
Optional, user-editable business context layered over introspected schemas. Includes table/column business descriptions, domain glossaries, sample value sets, and explicit/curated join hints.

### Intent Node
The agentic classification component that receives a user natural language prompt, determines the query intent type (lookup, aggregation, comparison, trend), extracts domain entities, and selects the relevant schema subset via vector retrieval.

### Agent Graph
The multi-step LangGraph state machine orchestrating query translation:
1. **Intent Node & Schema Linking** ->
2. **SQL Generation** ->
3. **Guardrailed SQL Execution** ->
4. **Self-Correction Retry Loop** (on execution error) ->
5. **Result Formatter** (NL summary + table data).

### Chat Session
A multi-turn conversational context checkpointed by LangGraph, allowing follow-up queries within a `Project` while retaining past query context and active filters.
