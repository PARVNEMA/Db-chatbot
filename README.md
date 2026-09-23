# 🤖 NL DB-Chatbot Platform

> **Ask your relational database anything in plain English.**
> An enterprise-grade, multi-tenant Natural Language to SQL query platform powered by **FastAPI**, **LangGraph**, **PostgreSQL with `pgvector`**, and **Next.js**.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6F00?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Next.js: 15](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![pgvector](https://img.shields.io/badge/pgvector-PostgreSQL%2017-336791?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [🛡️ Security & Guardrails (Deep Dive)](#️-security--guardrails-deep-dive)
- [Tech Stack](#-tech-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Quick Start Guide](#-quick-start-guide)
  - [Prerequisites](#prerequisites)
  - [Option A: Docker Compose (Recommended)](#option-a-docker-compose-recommended)
  - [Option B: Local Development Setup](#option-b-local-development-setup)
- [Environment Variables Reference](#-environment-variables-reference)
- [Step-by-Step User Journey](#-step-by-step-user-journey)
- [Testing & Quality Verification](#-testing--quality-verification)
- [Comprehensive Technical Documentation](#-comprehensive-technical-documentation)

---

## 🌟 Overview

The **NL DB-Chatbot Platform** enables non-technical team members (product managers, support leads, executives, analysts) to query complex operational and analytical databases using natural everyday language — without needing to write a single line of SQL.

Unlike naive Text-to-SQL tools that dump an entire raw schema into an LLM prompt and hope for the best, this platform employs a **structured, schema-aware agentic architecture**:
1. **Introspects & Caches Real Database Catalogs**: Reflects tables, columns, data types, primary keys, and foreign keys.
2. **Enriches Schema with Business Semantics**: Attaches business glossaries, column descriptions, and curated join hints.
3. **Retrieves Schema Subsets via Vector Similarity**: Utilizes HuggingFace sentence embeddings and `pgvector` to identify only the relevant tables and foreign key relationships for any given query.
4. **Validates & Executes with Ironclad Read-Only Guardrails**: Inspects SQL at the Abstract Syntax Tree (AST) level with `sqlglot` to guarantee no mutating statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) or semicolon injection attacks ever touch the target database.
5. **Self-Corrects on Execution Errors**: Features a bounded loop (up to 3 retries) where SQL execution or syntax errors are fed back to the LLM with error traces for automatic remediation.
6. **Streams Progress in Real Time via SSE**: Emits intermediate reasoning steps (intent detected, schema linked, SQL generated, query executed, result summarized) to the frontend via Server-Sent Events.

---

## 🚀 Key Features

- **Multi-Tenant Isolation by Design**: Every database connection, schema cache, vector embedding, and chat history is strictly namespaced by `project_id` and verified against authenticated users.
- **Dynamic Connection Engine**: Connects to target databases (PostgreSQL, MySQL, SQLite, MariaDB) with pooled asynchronous engines and on-demand credential decryption.
- **Automated Schema Ingestion & Embedding Sync**: One-click schema introspection automatically reflects tables and columns and generates 384-dimensional vector embeddings without secondary manual steps.
- **Semantic Layer & AI Auto-Suggestions**: Add custom business context, or click **"Auto-Suggest Descriptions"** to let an LLM draft domain glossaries and column meanings.
- **Stateful Conversational Memory**: LangGraph checkpointing preserves conversation state across multi-turn follow-ups (*"Filter that by the last 30 days"*, *"Break down the totals by category"*).
- **Dual-Output Presentation**: Returns both high-level natural language executive summaries and structured interactive data tables with pagination.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([👤 User / Browser]) <-->|Next.js 15 UI| Frontend[🖥️ Frontend Dashboard & Chat]
    Frontend <-->|REST API + SSE Stream| Backend[⚡ FastAPI Backend API]

    subgraph ControlPlane [Control Plane: Platform Services]
        Backend --> AuthService[Auth Service & JWT]
        Backend --> ProjectService[Project & Tenant Service]
        Backend --> IntroService[Schema Introspection Service]
        Backend --> SemanticService[Semantic Layer Service]
        Backend --> EmbeddingService[Embedding Service]
        Backend --> ChatService[Chat & Session Service]

        PlatformDB[(🗄️ PostgreSQL 17 + pgvector\nPlatform DB)]
        AuthService --> PlatformDB
        ProjectService --> PlatformDB
        IntroService --> PlatformDB
        SemanticService --> PlatformDB
        EmbeddingService <-->|HNSW Cosine <=> Search| PlatformDB
    end

    subgraph AgentOrchestrator [LangGraph Agent Pipeline]
        ChatService --> AgentGraph[Agent StateGraph]
        AgentGraph --> IntentNode[1. Intent Node & Vector Retrieval]
        IntentNode --> SQLGenNode[2. SQL Generator Node]
        SQLGenNode --> SQLExecNode[3. Guardrailed SQL Executor]
        SQLExecNode -->|AST Error / DB Error| RetryCheck{Retries < 3?}
        RetryCheck -->|Yes: Feed Error| SQLGenNode
        RetryCheck -->|No: Max Retries| ErrorNode[Error Terminal Node]
        SQLExecNode -->|Success| FormatterNode[4. Result Formatter Node]
    end

    subgraph DataPlane [Tenant Data Plane: Isolated Execution]
        SQLExecNode --> ConnMgr[ConnectionManager]
        ConnMgr -->|AST Validation via sqlglot| ASTCheck{AST Read-Only?}
        ASTCheck -->|Blocked| BlockedErr[Reject with Safe Error]
        ASTCheck -->|Allowed| Pool[Pooled AsyncEngine]
        Pool --> TargetDB[(🎯 Customer Target Database\nPostgres / MySQL / SQLite)]
    end
```

---

## 🛡️ Security & Guardrails (Deep Dive)

Security is not an afterthought in this platform; it is enforced across every architectural boundary from network ingestion to the target database socket.

```mermaid
flowchart LR
    A[Plaintext Password] -->|Fernet Symmetric Key| B[Encrypted Ciphertext at Rest]
    B -->|ConnectionManager Only| C[On-Demand Decrypted AsyncEngine]

    D[User Natural Language Prompt] -->|Regex Pre-Filter| E[Catch Unsafe Keywords Upfront]
    E -->|sqlglot AST Engine| F[Parse Root Statements & Expression Tree]
    F -->|Reject All DDL/DML/Admin| G[Execute Pure Single SELECT Statement]
```

### 1. Zero Plaintext Storage & Cryptographic Encryption
- **Fernet Symmetric Encryption at Rest**: Target database credentials, connection strings, and passwords are encrypted using Fernet (`app.core.security`) with keys derived via SHA-256 before being persisted to the platform database.
- **Strict Decryption Boundary**: Connection URLs are only decrypted on-demand within `ConnectionManager` at the exact millisecond an engine or test connection is initialized.
- **Zero Decrypted Leaks**: Raw connection strings and decrypted passwords are **never** returned in API responses, never rendered on the frontend, and stripped from application logs.
- **Credential Masking in Errors**: All database errors pass through `mask_connection_string()` (e.g., `postgresql://user:***@host:5432/db`) so connection failures never expose secrets in tracebacks.

### 2. Deep AST (Abstract Syntax Tree) Read-Only Guardrails (`sqlglot`)
String pattern matching is inadequate for SQL security. The platform deconstructs every generated SQL query into an Abstract Syntax Tree before sending it to the database:
- **Comment Stripping**: Automatically removes single-line (`--`) and multi-line (`/* */`) comments to neutralize hidden injection payloads.
- **Statement Whitelist**: Only root `SELECT`, `WITH ... SELECT` (Common Table Expressions), and set operations (`UNION`, `INTERSECT`, `EXCEPT`) are permitted.
- **Hard-Blocked Expressions**: If any node in the AST matches the following, execution is immediately aborted with a validation error:
  - **DML (Data Manipulation)**: `INSERT`, `UPDATE`, `DELETE`, `MERGE`
  - **DDL (Data Definition)**: `CREATE`, `DROP`, `ALTER`, `TRUNCATE`
  - **Permissions & Administration**: `GRANT`, `REVOKE`, `PRAGMA`, `EXEC`, `CALL`, `SET`
  - **Transaction Control**: `COMMIT`, `ROLLBACK`, `BEGIN`
- **Multi-Statement & Semicolon Prevention**: Disallows semicolon-separated query chaining (e.g., `SELECT 1; DROP TABLE users;`). Exactly one statement is allowed per execution turn.

### 3. Pre-Classification Intent Guardrail
Before invoking expensive LLM calls or schema searches, user input passes through a deterministic regex guardrail (`detect_unsafe_intent`). If a prompt asks to *"drop the customers table"* or *"delete from orders"*, the pipeline halts immediately, skips the LLM, and triggers an informative refusal message.

### 4. Strict Multi-Tenant Isolation
- **Row-Level Project Scoping**: Every database entity (`connections`, `schema_cache`, `schema_tables`, `schema_columns`, `schema_annotations`, `schema_embeddings`, `chat_sessions`, `chat_messages`, `query_runs`) has a foreign key to `project_id`.
- **Ownership Verification**: All route dependencies verify that the authenticated user owns the requested `project_id`. User A cannot query, introspect, or execute statements against User B's database.

### 5. Execution Timeouts & Memory Caps
- **Asynchronous Execution Timeout**: Target database queries are wrapped in `asyncio.wait_for(..., timeout=10.0)`. Runaway queries, cartesian product joins, or database lock contentions are automatically killed after 10 seconds.
- **Row Limit Caps**: Result sets are strictly fetched with `fetchmany(1000)` to eliminate out-of-memory risks.
- **Safe JSON Serialization**: Special database primitives (`Decimal`, `datetime`, `UUID`, binary data) are safely serialized into JSON-compliant types before reaching the agent or client.

### 6. Bounded Self-Correction Loop (Max 3 Retries)
If an LLM produces a query with a syntax error, invalid table alias, or non-existent column, the database error is caught and routed back to `sql_generator`. The loop is hard-capped at **3 retries**. If the query still fails, it terminates at `error_terminal_node`, preventing infinite LLM loops and resource exhaustion.

### 7. Recommended Target Database Hardening
For production deployments, we strongly recommend connecting your target database using a dedicated read-only database user:
```sql
-- PostgreSQL Read-Only User Setup Example
CREATE USER readonly_agent WITH PASSWORD 'secure_random_password';
GRANT CONNECT ON DATABASE analytics_db TO readonly_agent;
GRANT USAGE ON SCHEMA public TO readonly_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_agent;
```

---

## 💻 Tech Stack

| Domain | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance asynchronous REST API & SSE streaming |
| **Agent Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Deterministic state machine graph, conditional routing & self-correction |
| **LLM & Embeddings** | LangChain / Anthropic / Groq / OpenAI | Swappable chat models & HuggingFace sentence transformer embeddings |
| **AST SQL Parser** | [sqlglot](https://github.com/tobymao/sqlglot) | Syntactic AST validation, dialect conversion & read-only guardrails |
| **Platform Database** | [PostgreSQL 17](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) | Relational control plane data, metadata & HNSW vector cosine search |
| **Target DB Drivers** | `asyncpg`, `asyncmy`, `aiosqlite` | Asynchronous multi-dialect target database connectivity |
| **ORM & Migrations** | SQLAlchemy 2.0 (Async) + Alembic | Declarative database models, async sessions, and schema migrations |
| **Security & Crypto** | `cryptography` (Fernet) + `bcrypt` + `python-jose` | Credential encryption at rest, password hashing, and JWT tokens |
| **Frontend Framework**| [Next.js 15](https://nextjs.org/) (App Router) | Server & client React 19 components, Tailwind CSS styling |
| **Containerization** | Docker & Docker Compose | Multi-container development and production orchestration |

---

## 📁 Project Directory Structure

```text
Db-chatbot/
├── docker-compose.yml              # Multi-container orchestration (postgres, backend, frontend)
├── AGENTS.md                       # Mandatory backend architecture standards & API envelope rules
├── CONTEXT.md                      # Canonical domain terminology & definitions
├── README.md                       # Project overview, setup, and security guide (this file)
│
├── docs/                           # Architectural Decision Records & In-Depth Specs
│   ├── TECHNICAL_DOCUMENTATION.md  # Complete technical design & end-to-end execution flows
│   ├── Safety_measures_we_opt.md   # Security guardrails summary
│   ├── db_schema.md                # Platform database ER diagram and table specs
│   ├── embeddings_and_api_guide.md # Vector linking & schema search guide
│   └── adr/                        # Architecture Decision Records (ADR-0001 to ADR-0003)
│
├── backend/                        # FastAPI Backend Application
│   ├── Dockerfile                  # Production container definition
│   ├── pyproject.toml              # Dependencies, Ruff linter, and Pyright configuration
│   ├── alembic/                    # Database migration scripts
│   └── app/
│       ├── main.py                 # FastAPI application factory, middleware, and router mounts
│       ├── core/                   # Platform utilities: config, exceptions, security, responses, LLM
│       ├── db/                     # SQLAlchemy async engine, base model, and timestamp mixins
│       ├── crud/                   # Generic CRUDBase repository abstractions
│       ├── dependencies/           # FastAPI dependency injection (auth, db session, pagination)
│       └── domain/                 # Modular Domain-Driven Architecture (5-tier modules)
│           ├── auth/               # User registration, login, and JWT issuance
│           ├── projects/           # Multi-tenant project boundary management
│           ├── connections/        # ConnectionManager, pooling, Fernet encryption
│           ├── schema_introspection/# Database reflection & catalog caching
│           ├── semantic_layer/     # Business annotations, descriptions, glossaries
│           ├── embeddings/         # HuggingFace vector generation & pgvector similarity search
│           ├── agent/              # LangGraph StateGraph, nodes, prompts, AST sql_validator
│           └── chat/               # Chat sessions, message history, and SSE streaming
│
└── frontend/                       # Next.js 15 Client Application
    ├── Dockerfile                  # Frontend container definition
    ├── package.json                # Dependencies (Next 15, React 19, Tailwind, Lucide)
    └── src/
        ├── app/                    # Next.js App Router (auth, projects, schema, chat)
        ├── components/             # Reusable UI components (tables, modals, Monaco editor)
        ├── hooks/                  # Custom React hooks (useSSEChat, useProjects)
        └── lib/                    # API client, auth token helpers, and utility functions
```

---

## ⚡ Quick Start Guide

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.
- (For local manual setup): Python 3.11+, Node.js 18+, and a running PostgreSQL 15+ database with `pgvector`.

---

### Option A: Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/Db-chatbot.git
   cd Db-chatbot
   ```

2. **Configure environment variables**:
   Create `backend/.env` (you can copy the sample configuration from the [Environment Variables](#-environment-variables-reference) section below):
   ```bash
   cp backend/.env.example backend/.env   # or create manually
   ```

3. **Spin up all services**:
   ```bash
   docker compose up --build
   ```
   This will start:
   - **Platform Database (`postgres`)**: PostgreSQL 17 with `pgvector` on port `5432`.
   - **Backend API (`backend`)**: FastAPI application on `http://localhost:8000` (auto-reloads on edits).
   - **Frontend UI (`frontend`)**: Next.js 15 dashboard on `http://localhost:3000`.

4. **Run Alembic migrations** (in another terminal):
   ```bash
   docker compose exec backend alembic upgrade head
   ```

5. **Open the application**:
   Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

---

### Option B: Local Development Setup

#### 1. Backend Setup
```bash
cd backend
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The frontend will start at [http://localhost:3000](http://localhost:3000).

---

## ⚙️ Environment Variables Reference

Create a `.env` file inside the `backend/` directory with the following variables:

```env
# ── Application & Control Plane DB ──────────────────────────────────────────
PROJECT_NAME="Natural Language Database Querying Platform"
API_V1_STR="/api/v1"
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/platform_db

# ── Cryptography & Security ──────────────────────────────────────────────────
# JWT Secret for access token generation
JWT_SECRET_KEY=your_super_secret_jwt_key_at_least_32_characters_long
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 32-byte URL-safe base64 key or arbitrary passphrase for Fernet DB encryption
# (You can generate one via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FERNET_KEY=YOUR_GENERATED_32_BYTE_BASE64_FERNET_KEY=

# ── LLM Provider Configuration ──────────────────────────────────────────────
# Supported providers: anthropic, openai, groq, huggingface
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022

# API Keys (Provide the one corresponding to your chosen LLM_PROVIDER):
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
HUGGINGFACE_API_TOKEN=hf_...

# ── Embedding Model Configuration ────────────────────────────────────────────
# Hugging Face sentence transformer model for schema embeddings (default: 384 dimensions)
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

---

## 🗺️ Step-by-Step User Journey

```text
[1. Sign Up / Login]
         │
         ▼
[2. Create Project] ──────────► Multi-tenant workspace created with UUID
         │
         ▼
[3. Connect Database] ────────► Input DB URI -> Connectivity tested -> Encrypted via Fernet
         │
         ▼
[4. Auto-Introspect Schema] ──► Tables/columns extracted -> 384d vector embeddings generated
         │
         ▼
[5. Semantic Enrichment] ────► (Optional) Click 'Auto-Suggest' or add business glossary hints
         │
         ▼
[6. Chat in Natural Language] ► Ask questions -> Watch real-time SSE stream -> Review SQL & Data
```

1. **Register & Log In**: Create an account with email and password (passwords hashed via `bcrypt`, sessions authenticated via JWT).
2. **Create a Project**: Establish an isolated project workspace (e.g., *"E-Commerce Analytics"*).
3. **Connect Your Database**: Enter your database dialect and connection string. Click **"Test Connection"** to verify connectivity and latency. Upon saving, credentials are encrypted via Fernet.
4. **Introspect Schema**: Click **"Introspect Schema"**. The system inspects your target database's catalogs, caches table and column definitions, and immediately generates vector embeddings.
5. **Enrich Semantics (Optional)**: Open the Schema Explorer to view table relationships. Add business notes or click **"Auto-Suggest Descriptions"** to let the LLM draft contextual summaries.
6. **Chat with Your Data**: Open the Chat interface and submit queries in plain English (*"Show me the top 5 customers with the most cancelled orders last quarter"*). Watch the live step-by-step agent execution, inspect the generated SQL, view raw tables, and read the natural language executive summary.

---

## 🧪 Testing & Quality Verification

To ensure reliability, strict type safety, and regression prevention, the repository includes a standardized verification suite:

```bash
# Activate your backend virtual environment
cd backend

# 1. Run automated unit and integration tests
pytest

# 2. Run Ruff linting and formatting checks
ruff check .
ruff format --check .

# 3. Run Pyright static type checker
pyright
```

---


## 📄 License

This project is licensed under the [MIT License](LICENSE).
