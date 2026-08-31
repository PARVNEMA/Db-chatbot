"""
Embeddings domain — Pydantic v2 schemas.

Defines schemas for vector similarity search requests/results and embedding generation responses.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SchemaSearchRequest(BaseModel):
    """Payload for natural language schema vector search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or concept to match against database schema",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of relevant schema columns to retrieve",
    )


class SchemaSearchResult(BaseModel):
    """Single matching column result from vector search."""

    model_config = ConfigDict(from_attributes=True)

    column_id: uuid.UUID
    table_id: uuid.UUID
    schema_name: str | None = None
    table_name: str
    column_name: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    fk_target_table: str | None = None
    fk_target_column: str | None = None
    embed_text: str
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class TableGroupedSearchResult(BaseModel):
    """Schema search results grouped by parent table."""

    table_id: uuid.UUID
    schema_name: str | None = None
    table_name: str
    matched_columns: list[SchemaSearchResult] = Field(default_factory=list)


class EmbeddingGenerateResponse(BaseModel):
    """Response returned when triggering embedding generation."""

    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    connection_id: uuid.UUID
    embedded_columns_count: int
    model: str
    dimensions: int


class AutoSuggestRequest(BaseModel):
    """Payload for auto-suggesting schema annotations for a specific table."""

    table_id: uuid.UUID = Field(
        ...,
        description="Compulsory UUID of the schema table to auto-suggest descriptions for",
    )


class AutoSuggestResponse(BaseModel):
    """Response returned when auto-suggesting schema annotations."""

    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    connection_id: uuid.UUID
    table_id: uuid.UUID
    table_name: str
    table_description: str | None = None
    column_descriptions: dict[str, str] = Field(default_factory=dict)
    suggested_tables_count: int = 1
    suggested_columns_count: int = 0
    model: str

