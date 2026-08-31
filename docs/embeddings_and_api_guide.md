# Schema Embeddings & API Architecture Guide

This document explains how schema embeddings, vector search, auto-suggestions, and database introspection interact in the platform.

---

## 1. High-Level Architecture & API Map

```mermaid
graph TD
    User["Client / UI / Agent"] -->|1. Introspect DB| API_Introspect["POST /projects/{id}/schema/introspect"]
    User -->|2. Search Schema| API_Search["POST /projects/{id}/schema/search"]
    User -->|3. Auto-Suggest Descriptions| API_Suggest["POST /projects/{id}/schema/auto-suggest"]
    User -->|4. Manage Annotations| API_Annot["POST / PUT / DELETE /projects/{id}/annotations"]
    User -->|5. Manual Re-embed| API_Embed["POST /projects/{id}/schema/embeddings/generate"]

    subgraph Backend Domain Services
        API_Introspect --> IntrospectService["SchemaIntrospectionService"]
        API_Search --> EmbeddingService["EmbeddingService"]
        API_Suggest --> EmbeddingService
        API_Annot --> SemanticService["SemanticLayerService"]
        API_Embed --> EmbeddingService

        IntrospectService -->|Internal Call: Auto-trigger| EmbeddingService
        SemanticService -->|Internal Call: Sync Embeddings| EmbeddingService
    end

    subgraph AI Factory
        EmbeddingService -->|Generate Vectors| HF["app.core.llm -> HuggingFaceEmbeddings (384d)"]
        EmbeddingService -->|Draft Descriptions| LLM["app.core.llm -> Swappable ChatLLM (Groq/HF/OpenAI)"]
    end

    subgraph Storage
        EmbeddingService -->|Upsert Vectors & <=> Search| PG["PostgreSQL (pgvector: schema_embeddings)"]
    end
```

---

## 2. API Endpoints Overview

| Method | Endpoint | Purpose | Internal Action |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/projects/{id}/schema/introspect` | Scans target database tables & columns | Saves schema **AND automatically generates embeddings** for all columns |
| `POST` | `/api/v1/projects/{id}/schema/search` | Natural language schema linking | Embeds user query → performs pgvector `<=>` cosine similarity search |
| `POST` | `/api/v1/projects/{id}/schema/auto-suggest` | Uses LLM to draft descriptions for a specific table (`table_id`) & its columns | Prompts LLM for descriptions → saves `SchemaAnnotation` → re-embeds |
| `POST` | `/api/v1/projects/{id}/schema/embeddings/generate` | Manual vector regeneration | Reconstructs composite text for all columns and stores 384d vectors |
| `POST/PUT/DELETE` | `/api/v1/projects/{id}/annotations` | User edits table/column notes | Updates annotation record → immediately syncs vector for that column |

---

## 3. What Happens During Introspection?

When you call `POST /api/v1/projects/{project_id}/schema/introspect`:

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Router as Schema Router
    participant IntroService as SchemaIntrospectionService
    participant TargetDB as User Target Database
    participant EmbeddingService as EmbeddingService
    participant HF as Hugging Face Inference API
    participant PlatformDB as Platform PostgreSQL (pgvector)

    Client->>Router: POST /projects/{id}/schema/introspect
    Router->>IntroService: introspect_schema(project_id)
    IntroService->>TargetDB: Reflect tables, columns, PKs, FKs
    TargetDB-->>IntroService: Raw Schema Metadata
    IntroService->>PlatformDB: Persist SchemaCache, SchemaTables, SchemaColumns
    
    rect rgb(240, 248, 255)
    note right of IntroService: Internal Embedding Trigger (No separate HTTP call required)
    IntroService->>EmbeddingService: generate_and_store_for_connection(project_id, connection_id)
    EmbeddingService->>EmbeddingService: Build composite embed_text per column
    EmbeddingService->>HF: embed_documents([embed_text_1, ...])
    HF-->>EmbeddingService: 384-dimensional vector arrays
    EmbeddingService->>PlatformDB: Bulk upsert into schema_embeddings
    end

    IntroService-->>Router: IntrospectResponse (table & column summary)
    Router-->>Client: 200 OK + ApiResponse
```

### Key Detail:
* **No secondary HTTP call is needed.** 
* When `POST /projects/{id}/schema/introspect` runs, `SchemaIntrospectionService` directly invokes `EmbeddingService.generate_and_store_for_connection()` in the backend so embeddings are immediately generated and searchable.

---

## 4. Structure of Composite `embed_text`

Every column embedding bakes in its parent table context + business descriptions into one searchable string:

```text
Table: public.orders
Columns: id, customer_id, total_amount, status, created_at
Primary Keys: id
Foreign Keys: customer_id -> customers.id
---
Column: total_amount
Type: NUMERIC(10,2)
Nullable: no
Primary Key: no
Foreign Key: no
---
Table Description: Customer sales orders and checkout transactions
Column Description: Total final monetary amount billed to the customer
```

---

## 5. Schema Search Flow (`POST /schema/search`)

```mermaid
sequenceDiagram
    actor Client
    participant Router as Embeddings Router
    participant Service as EmbeddingService
    participant HF as Hugging Face Embeddings
    participant DB as pgvector

    Client->>Router: POST /schema/search ("What is the total revenue?")
    Router->>Service: search_schema(query="What is the total revenue?", top_k=5)
    Service->>HF: embed_query("What is the total revenue?")
    HF-->>Service: Query Vector [0.034, -0.112, ...] (384d)
    Service->>DB: SELECT * FROM schema_embeddings ORDER BY embedding <=> query_vector LIMIT 5
    DB-->>Service: Ranked Columns (orders.total_amount, payments.amount, ...)
    Service-->>Router: Ranked SchemaSearchResult list
    Router-->>Client: 200 OK + Matches with similarity scores
```
