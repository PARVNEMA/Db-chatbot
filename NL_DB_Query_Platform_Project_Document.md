# Natural Language Database Querying Platform
### Project Document

---

## 1. Executive Summary

The **Natural Language Database Querying Platform** is a multi-database, agentic system that allows users to connect any supported database (via connection string) and ask questions in plain English, which the system translates into accurate SQL, executes safely, and returns human-readable results.

The platform is designed around three core principles:

1. **Schema-aware, not schema-blind** — the system introspects the actual database structure and optionally layers business/semantic context on top, rather than relying purely on an LLM's guess.
2. **Structured reasoning over one-shot generation** — a dedicated intent and schema-linking stage narrows down relevant tables/columns before query generation, improving accuracy and reducing hallucination.
3. **Built for multi-tenancy from day one** — every component (schema cache, embeddings, credentials, chat state) is namespaced by project/connection, so the same core engine can later power multiple independent, embeddable chatbots — one per database/project.

**Target users:** teams who want to query their operational or analytical databases in natural language without writing SQL — product managers, support teams, analysts, and eventually external end-customers via embedded chatbots.

---

## 2. Problem Statement

- Writing SQL requires technical skill; most business stakeholders can't self-serve data answers.
- Existing "text-to-SQL" tools often fail on real-world schemas because they either:
  - Dump the entire schema into the prompt (breaks down on large schemas, causes hallucinated joins), or
  - Rely solely on naming conventions without understanding actual relationships and business meaning.
- Most tools are single-database, single-tenant, and not designed to scale into a multi-project, multi-customer product.

---

## 3. Goals & Non-Goals

### Goals
- Accept a DB connection string (Postgres, MySQL, SQL Server, Snowflake, etc.) and auto-discover schema.
- Allow optional semantic enrichment (business glossary, column descriptions, sample values).
- Convert natural language → correct, dialect-aware SQL.
- Execute safely (read-only by default, timeouts, row limits).
- Return results in both raw (table) and natural-language-summarized form.
- Support follow-up/conversational queries ("now filter that by last month").
- Be architected so each connected database can later become its own standalone chatbot.

### Non-Goals (for v1)
- Writing back to the database (INSERT/UPDATE/DELETE) — read-only only, initially.
- Cross-database joins in a single query.
- Full BI/dashboarding features (charts can come later as a lightweight layer).

---

## 4. High-Level Architecture

```
User NL Query
     │
     ▼
 Intent Node ───────► Current DB Summary (schema + semantic context, retrieved)
     │
     ▼
 Query Generate ───► (dialect-specific SQL)
     │
     ▼
 Query Execute ───► [Error?] ──► loop back to Query Generate (bounded retries)
     │
     ▼
 Result Formatter (NL summary + raw table)
     │
     ▼
 Return Result
```

### Core components

| Component | Responsibility |
|---|---|
| **Connection Manager** | Validates & stores encrypted connection strings; manages pooled connections per project |
| **Schema Introspector** | Pulls tables, columns, types, PKs/FKs via `information_schema` / dialect-specific reflection |
| **Semantic Layer** | Optional, editable metadata: descriptions, glossary terms, sample values, curated join hints |
| **Vector Store** | Embeddings of table/column descriptions for retrieval-based schema linking (scales to large schemas) |
| **Intent Node** | Classifies query type (lookup, aggregation, comparison, trend), extracts entities, retrieves relevant schema subset |
| **Query Generator** | LLM-driven SQL generation, constrained to retrieved schema subset and target dialect |
| **Query Executor** | Executes with read-only role, timeout, row-limit guardrails |
| **Self-Correction Loop** | On execution error, feeds error back to Query Generator (max N retries) |
| **Result Formatter** | Summarizes result set in natural language + returns structured table data |
| **Session/State Manager** | LangGraph checkpointing for multi-turn conversations, scoped per project + session |
| **Project/Tenant Layer** | Namespaces everything above by project ID, enabling future per-DB chatbot spin-up |

---

## 5. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| **Orchestration** | LangGraph | State machine / graph orchestration, built-in checkpointing for multi-turn memory |
| **LLM Framework** | LangChain | Tool calling, DB toolkits, prompt management |
| **LLM Provider** | Claude (Anthropic API) | Reasoning + SQL generation; swappable via LangChain abstraction |
| **Backend API** | FastAPI (Python) | Async, good fit with LangChain/LangGraph ecosystem |
| **DB Connectivity** | SQLAlchemy + dialect drivers (psycopg2, pymysql, pyodbc, snowflake-connector) | Unified reflection + query execution interface |
| **Vector Store** | pgvector (if Postgres already in stack) or Chroma | Schema-linking retrieval for large schemas |
| **Metadata/App DB** | PostgreSQL | Stores projects, encrypted connection strings, semantic layer metadata, chat history |
| **Cache** | Redis | Schema cache, rate limiting, session state |
| **Secrets/Encryption** | AWS KMS / HashiCorp Vault (or Fernet for MVP) | Encrypt connection strings at rest |
| **Frontend** | Next.js (App Router) + React + Tailwind CSS | Chat UI, schema explorer, connection setup wizard |
| **Observability** | LangSmith | Tracing agent decisions, debugging wrong joins/queries |
| **Auth** | OAuth2 / JWT (Auth0 or custom) | Especially needed once multi-tenant chatbots go external |
| **Deployment** | Docker + Kubernetes (or simpler: Docker Compose → ECS/Fargate for MVP) | |

---

## 6. Implementation Phases

### Phase 0 — Foundations (1–2 weeks)
- Set up repo structure, CI/CD, base FastAPI service.
- Design core data model: `Project`, `Connection`, `SchemaCache`, `SemanticMetadata`, `ChatSession`.
- Implement encrypted connection string storage.

### Phase 1 — Schema Introspection (2 weeks)
- Build DB adapters (Postgres first, then MySQL) using SQLAlchemy reflection.
- Extract tables, columns, types, PK/FK relationships.
- Cache introspected schema in the metadata DB.
- Build a basic schema explorer UI (view tables/columns before querying).

### Phase 2 — Semantic Enrichment Layer (1–2 weeks)
- Editable metadata layer: table/column descriptions, glossary, sample values, manual join hints.
- Store as structured JSON keyed to introspected schema.
- Embed descriptions into vector store for retrieval.

### Phase 3 — Core Agent Graph (3–4 weeks)
- Build LangGraph pipeline: Intent Node → Schema Retrieval → Query Generate → Query Execute → Result Formatter.
- Implement dialect-aware prompt templates for SQL generation.
- Add guardrails: read-only DB role, query timeout, row limits, blocked DDL/DML keywords.
- Implement self-correction loop (execution error → retry, capped at ~3 attempts).

### Phase 4 — Conversational Memory (1–2 weeks)
- Add LangGraph checkpointing for multi-turn follow-up queries.
- Session-scoped context (last query, last result set, active filters).

### Phase 5 — Result Presentation (1 week)
- Natural language summary of results.
- Tabular display + basic chart suggestions (optional, simple bar/line via a charting lib).

### Phase 6 — Testing & Hardening (2 weeks)
- Test against multiple real-world schemas (varying size/complexity).
- Adversarial testing: ambiguous queries, missing joins, large schemas.
- Add LangSmith tracing for observability and debugging accuracy issues.
- Security review: SQL injection resistance, credential handling, access scoping.

### Phase 7 — MVP Launch
- Onboarding flow: connect DB → auto-introspect → optional semantic enrichment → start chatting.
- Basic usage analytics (queries run, success/failure rate, common failure patterns).

---

## 7. Future Scope: Per-Project Standalone Chatbots

Because everything above is namespaced by `project_id` from Phase 0, spinning up a dedicated chatbot per database becomes primarily a packaging/deployment exercise rather than a rearchitecture:

- **Embeddable widget**: a lightweight chat widget (iframe or JS snippet) scoped to one `project_id`, calling the same backend API.
- **Per-project isolation**: separate vector namespace, separate chat history, separate rate limits/quotas per project.
- **Access control**: API keys or JWTs scoped to a project, so external end-customers only ever query their own DB's chatbot.
- **Branding/customization layer**: per-project chatbot name, logo, welcome message — cosmetic layer on top of the shared engine.
- **Usage-based billing hooks**: since queries are already logged per project, this plugs directly into metering/billing later.

No core pipeline changes needed later — this only works cleanly *if* the namespacing discipline is followed from Phase 0.

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Wrong joins on complex schemas | Semantic layer with curated join hints + retrieval-based schema linking |
| SQL injection / destructive queries | Read-only DB role, blocked DDL/DML, parameterized execution |
| Large schema context overflow | Vector-store retrieval instead of full schema dump |
| Ambiguous user queries | Intent node asks clarifying questions before generating SQL |
| Cost (LLM calls per query) | Cache repeated query patterns, use smaller model for intent classification |
| Connection string leakage | Encryption at rest (KMS/Vault), never log raw credentials |

---

## 9. Success Metrics (MVP)

- **Query accuracy rate**: % of natural language queries producing correct, executable SQL without manual correction.
- **Self-correction success rate**: % of initially failed queries fixed automatically via the retry loop.
- **Time-to-first-result**: from connection string input to first successful query.
- **Schema size supported**: number of tables handled with acceptable accuracy (target: 50+ tables via retrieval).
