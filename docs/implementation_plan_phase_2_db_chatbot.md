# Implementation Plan: Semantic Layer + Embedding Generation + Vector Search

## Overview

Implement Phase 2 of the NL-DB platform: a complete Semantic Layer CRUD system, composite embedding generation (structural metadata + semantic annotations in a single `embed_text` per column), and pgvector-based similarity search for schema linking. This covers the full pipeline from user annotations → embedding generation → vector retrieval at query time.

## Architecture Decisions

- **Centralized AI Config Factory (`app/core/llm.py`)**: A single file that exposes `get_embeddings_client()` and `get_llm_client()` factory functions, configured via `app/core/config.py` settings. Every service in the project imports from here — never instantiates LLM/embedding clients directly. Changing provider or model is a one-line `.env` change.
- **Hugging Face Inference API for Embeddings**: Use `langchain-huggingface` + `huggingface_hub` with the HF Serverless Inference API. Default model configurable (e.g. `BAAI/bge-small-en-v1.5` at 384 dims, or `sentence-transformers/all-MiniLM-L6-v2` at 384 dims). Requires updating the `SchemaEmbedding` pgvector column dimension + Alembic migration.
- **Swappable LLM for Auto-Suggest**: Auto-suggest uses `get_llm_client()` from `app/core/llm.py`, not a hardcoded provider. Supports HuggingFace Inference, Anthropic, OpenAI, Groq, etc. via `LLM_PROVIDER` setting.
- **Single composite `embed_text` per column**: Each column's embedding bakes in its parent table context (table name, schema, all sibling column names, FK relationships) plus any user-provided semantic annotations. One vector search returns columns with full table context — no separate table-level embeddings needed.
- **Auto-generation trigger**: Embeddings are auto-generated/regenerated when: (a) schema is introspected, (b) annotations are created/updated/deleted. This keeps embeddings always in sync.
- **Domain boundaries**: Embedding logic lives in a new `app/domain/embeddings/` domain module. Semantic layer CRUD lives in `app/domain/semantic_layer/`. Neither directly imports the other's repository — they communicate via service-to-service calls.

---

## Proposed Changes & Task Progress

### Phase 1: Foundation — AI Config + Dependencies

---

#### Task 1: Centralized AI Config Factory + Dependencies (DONE)

**Description:** Create `app/core/llm.py` as the single source of truth for all AI model instantiation across the project. Add HuggingFace and provider-related settings to `app/core/config.py`. Add required dependencies. Create Alembic migration to update pgvector embedding dimension.

**Acceptance criteria:**
- [x] New settings added to [`app/core/config.py`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/core/config.py):
  - `HUGGINGFACE_API_KEY: str`
  - `EMBEDDING_PROVIDER: str` (default `"huggingface"`, supports `"openai"`)
  - `EMBEDDING_MODEL: str` (default `"BAAI/bge-small-en-v1.5"`)
  - `EMBEDDING_DIMENSIONS: int` (default `384`)
  - `LLM_PROVIDER: str` (default `"huggingface"`, supports `"anthropic"`, `"openai"`, `"groq"`)
  - `LLM_MODEL: str` (default e.g. `"mistralai/Mistral-7B-Instruct-v0.3"`)
  - `LLM_TEMPERATURE: float` (default `0.0`)
  - `LLM_MAX_TOKENS: int` (default `4096`)
  - `OPENAI_API_KEY: str` (optional, for when provider is `"openai"`)
  - `GROQ_API_KEY: str` (optional, for when provider is `"groq"`)
- [x] New file `app/core/llm.py` [NEW] with:
  - `get_embeddings_client() -> Embeddings` — returns `HuggingFaceEndpointEmbeddings` or `OpenAIEmbeddings` based on `settings.EMBEDDING_PROVIDER`
  - `get_llm_client(temperature=None, max_tokens=None) -> BaseChatModel` — returns HF Inference / ChatAnthropic / ChatOpenAI / ChatGroq based on `settings.LLM_PROVIDER`
- [x] Dependencies added to [`requirements.txt`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/requirements.txt): `langchain-huggingface`, `huggingface-hub`, `langchain-openai`, `langchain-groq`
- [x] Alembic migration to alter `schema_embeddings.embedding` column from `Vector(1536)` to `Vector(384)` (matching HF default model dimension)
- [x] Update [`SchemaEmbedding`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/domain/schema_introspection/models.py#L161-L190) model: change `Vector(1536)` → `Vector(384)`, update default `model` string

---

### Phase 2: Semantic Layer CRUD

---

#### Task 2: Semantic Layer Schemas (DONE)

**Description:** Implement Pydantic v2 request/response schemas for creating, updating, reading, and listing schema annotations (table and column descriptions).

**Acceptance criteria:**
- [x] `AnnotationCreate` schema with fields: `target_type` (Literal["table", "column"]), `schema_table_id` (optional UUID), `schema_column_id` (optional UUID), `note` (str), `is_auto_generated` (bool)
- [x] `AnnotationUpdate` schema with field: `note` (str)
- [x] `AnnotationResponse` schema with all fields including `id`, `project_id`, `connection_id`, `target_type`, `note`, `is_auto_generated`, `created_at`, `updated_at` — with `model_config = ConfigDict(from_attributes=True)`
- [x] Proper validation: exactly one of `schema_table_id` / `schema_column_id` must be set based on `target_type`

---

#### Task 3: Semantic Layer Repository (DONE)

**Description:** Implement the data access layer for `SchemaAnnotation` CRUD operations with strict `project_id` tenant isolation.

**Acceptance criteria:**
- [x] `create_annotation()` — insert a new annotation
- [x] `get_annotation()` — fetch single annotation by ID, scoped by `project_id`
- [x] `get_annotations_for_connection()` — list all annotations for a connection, with optional `target_type` filter
- [x] `get_annotations_for_table()` — all annotations for a specific table (table-level + its column-level)
- [x] `update_annotation()` — update note text
- [x] `delete_annotation()` — delete by ID
- [x] `delete_annotations_for_connection()` — bulk delete (used when connection/schema is re-introspected)
- [x] All queries enforce `project_id` filtering

---

#### Task 4: Semantic Layer Service + Router (DONE)

**Description:** Implement the business logic service and REST API endpoints for managing schema annotations. After each annotation CUD operation, trigger embedding regeneration for affected columns.

**Acceptance criteria:**
- [x] Service methods: `create_annotation`, `get_annotation`, `list_annotations`, `update_annotation`, `delete_annotation`
- [x] Ownership validation: verify user owns the project before any operation
- [x] After create/update/delete, call embedding service to regenerate affected column embeddings
- [x] Router endpoints:
  - `POST /{project_id}/annotations` → create annotation
  - `GET /{project_id}/annotations` → list annotations (with optional `target_type` query param)
  - `GET /{project_id}/annotations/{annotation_id}` → get single annotation
  - `PUT /{project_id}/annotations/{annotation_id}` → update annotation
  - `DELETE /{project_id}/annotations/{annotation_id}` → delete annotation
- [x] All endpoints use `ApiResponse[...]` envelope and proper status codes
- [x] Router mounted in [`app/main.py`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/main.py) under `/api/v1/projects`

---

### Phase 3: Embedding Generation + Vector Search

---

#### Task 5: Embedding Domain — Composite `embed_text` Builder + HuggingFace Client (DONE)

**Description:** Create a new `app/domain/embeddings/` domain module with a service that: (a) composes rich `embed_text` strings from structural metadata + semantic annotations, and (b) calls HuggingFace Inference API via `get_embeddings_client()` from `app/core/llm.py`.

**Acceptance criteria:**
- [x] `app/domain/embeddings/__init__.py` created
- [x] `app/domain/embeddings/services.py` with `EmbeddingService` class containing:
  - `build_composite_embed_text(column, table, table_annotations, column_annotations)` — pure function composing the text
  - `generate_embeddings_batch(texts: list[str]) -> list[list[float]]` — batch call via `get_embeddings_client()` from `app/core/llm.py`
  - `generate_and_store_for_connection(project_id, connection_id)` — orchestrates full pipeline: fetch all tables/columns + annotations → build embed_text for each column → batch embed → upsert into `schema_embeddings`
  - `regenerate_for_column(project_id, connection_id, column_id)` — targeted single-column regeneration (called after annotation updates)
- [x] Uses `get_embeddings_client()` — never instantiates HF client directly
- [x] Handles API errors gracefully with logging (never crashes the annotation flow)
- [x] Batch embedding calls in chunks of 50 for safety

---

#### Task 6: Embedding Repository + Wiring into Semantic Layer & Introspection (DONE)

**Description:** Create the embedding repository for upsert/delete/search operations, and wire embedding regeneration into both the semantic layer service (annotation CUD) and schema introspection service (after re-introspect).

**Acceptance criteria:**
- [x] `app/domain/embeddings/repository.py` with `EmbeddingRepository` class containing:
  - `upsert_embedding(column_id, project_id, connection_id, embed_text, embedding, model)` — insert or update
  - `bulk_save_embeddings(embeddings_data: list)` — atomic replace
  - `delete_for_connection(project_id, connection_id)` — bulk delete
  - `delete_for_column(project_id, column_id)` — single delete
- [x] [`SemanticLayerService`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/domain/semantic_layer/services.py) calls `EmbeddingService.regenerate_for_column()` or `generate_and_store_for_connection()` after annotation create/update/delete
- [x] [`SchemaIntrospectionService.introspect_schema()`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/domain/schema_introspection/services.py) calls `EmbeddingService.generate_and_store_for_connection()` after saving introspected schema
- [x] All queries enforce `project_id` filtering

---

#### Task 7: Vector Similarity Search Service + Endpoint (DONE)

**Description:** Implement pgvector cosine similarity search to retrieve the most relevant columns (with table context) for a given natural language query. This is the core schema-linking retrieval used by the Intent Node in Phase 3.

**Acceptance criteria:**
- [x] `app/domain/embeddings/schemas.py` [NEW] with:
  - `SchemaSearchRequest` — `query: str`, `top_k: int = 10`
  - `SchemaSearchResult` — `column_id`, `table_name`, `schema_name`, `column_name`, `data_type`, `is_primary_key`, `is_foreign_key`, `fk_target_table`, `fk_target_column`, `embed_text`, `similarity_score`
  - `EmbeddingGenerateResponse` — status and counts
- [x] `EmbeddingRepository.search_similar(project_id, connection_id, query_embedding, top_k)` — pgvector `<=>` (cosine distance) operator with fallback support
- [x] `EmbeddingService.search_schema(project_id, user_id, query, top_k)` — embeds query via `get_embeddings_client()` → calls repo search → returns ranked results
- [x] Router endpoint: `POST /{project_id}/schema/search` with `SchemaSearchRequest` body → returns `ApiResponse[list[SchemaSearchResult]]`
- [x] Router endpoint: `POST /{project_id}/schema/embeddings/generate`
- [x] Router mounted in [`app/main.py`](file:///c:/Users/Lenovo/OneDrive/Desktop/Db-chatbot/backend/app/main.py)

---

### Phase 4: LLM Auto-Suggest Descriptions

---

#### Task 8: Auto-Suggest Annotations via Swappable LLM (DONE)

**Description:** After introspection, use the configured LLM (via `get_llm_client()` from `app/core/llm.py`) to auto-generate draft table and column descriptions from the structural schema. Users can review and edit these in the Schema Explorer. The LLM provider is NOT hardcoded — it uses whatever `LLM_PROVIDER` / `LLM_MODEL` is configured.

**Acceptance criteria:**
- [x] `EmbeddingService.auto_suggest_descriptions(project_id, user_id)` — sends introspected schema to the configured LLM with a structured prompt, parses response into per-table and per-column descriptions
- [x] Uses `get_llm_client()` from `app/core/llm.py` — swappable LLM (Hugging Face, Anthropic, OpenAI, Groq)
- [x] Auto-created annotations are marked with a flag (`is_auto_generated: bool` column on `SchemaAnnotation` model with Alembic migration `c2d3e4f5a6b7_add_is_auto_generated_to_annotations.py`)
- [x] Endpoint: `POST /{project_id}/schema/auto-suggest` — triggers auto-suggest, creates draft annotations, then generates embeddings
- [x] Does NOT overwrite existing user-edited annotations (only creates where none exist)
- [x] Switching `LLM_PROVIDER` / `LLM_MODEL` in `.env` changes the auto-suggest model project-wide

---

## Test & Verification Results

- **Linting (`ruff check .`)**: Passed with 0 errors.
- **Unit & API Test Suite (`pytest`)**: 43/43 tests passed across all domain modules (`connections`, `projects`, `schema_introspection`, `semantic_layer`, `embeddings`, `core.llm`, `integration`).
