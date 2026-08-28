"""
Embeddings domain — service layer.

Orchestrates composite `embed_text` construction, batch embedding generation via
the centralized AI model factory (`app.core.llm`), and vector similarity search.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator, Sequence
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.llm import get_embeddings_client, get_llm_client
from app.dependencies.auth import DbSession
from app.domain.connections.services import ConnectionService, get_connection_service
from app.domain.embeddings.repository import EmbeddingRepository
from app.domain.embeddings.schemas import AutoSuggestResponse, SchemaSearchResult
from app.domain.schema_introspection.models import SchemaColumn, SchemaTable
from app.domain.schema_introspection.repository import SchemaIntrospectionRepository
from app.domain.semantic_layer.models import SchemaAnnotation
from app.domain.semantic_layer.repository import SchemaAnnotationRepository

logger = logging.getLogger(__name__)


def build_composite_embed_text(
    column: SchemaColumn,
    table: SchemaTable,
    table_annotations: Sequence[SchemaAnnotation] | None = None,
    column_annotations: Sequence[SchemaAnnotation] | None = None,
) -> str:
    """Build a rich composite string fusing structural schema metadata and business descriptions."""
    # Sibling columns summary
    col_names = [c.column_name for c in table.columns] if table.columns else [column.column_name]
    pk_cols = [c.column_name for c in table.columns if c.is_primary_key] if table.columns else []
    if column.is_primary_key and column.column_name not in pk_cols:
        pk_cols.append(column.column_name)

    fk_links: list[str] = []
    if table.columns:
        for c in table.columns:
            if c.is_foreign_key and c.fk_target_table:
                fk_links.append(f"{c.column_name} -> {c.fk_target_table}.{c.fk_target_column or 'id'}")
    elif column.is_foreign_key and column.fk_target_table:
        fk_links.append(f"{column.column_name} -> {column.fk_target_table}.{column.fk_target_column or 'id'}")

    # Notes
    t_notes = [a.note for a in (table_annotations or []) if a.note.strip()]
    c_notes = [a.note for a in (column_annotations or []) if a.note.strip()]
    table_desc = "; ".join(t_notes) if t_notes else "No table description provided"
    col_desc = "; ".join(c_notes) if c_notes else "No column description provided"

    schema_prefix = f"{table.schema_name}." if table.schema_name else ""
    fk_summary = ", ".join(fk_links) if fk_links else "None"
    pk_summary = ", ".join(pk_cols) if pk_cols else "None"
    nullable_str = "yes" if column.is_nullable else "no"
    pk_str = "yes" if column.is_primary_key else "no"
    fk_target = (
        f"{column.fk_target_table}.{column.fk_target_column or 'id'}"
        if column.is_foreign_key
        else "no"
    )

    return (
        f"Table: {schema_prefix}{table.table_name}\n"
        f"Columns: {', '.join(col_names)}\n"
        f"Primary Keys: {pk_summary}\n"
        f"Foreign Keys: {fk_summary}\n"
        f"---\n"
        f"Column: {column.column_name}\n"
        f"Type: {column.data_type}\n"
        f"Nullable: {nullable_str}\n"
        f"Primary Key: {pk_str}\n"
        f"Foreign Key: {fk_target}\n"
        f"---\n"
        f"Table Description: {table_desc}\n"
        f"Column Description: {col_desc}"
    )


def _parse_auto_suggest_json(response_text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Extract and parse JSON tables and columns from LLM response text."""
    import json
    import re

    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
    json_str = match.group(1) if match else response_text

    try:
        parsed = json.loads(json_str)
    except Exception as parse_err:
        logger.warning("Failed to parse LLM auto-suggest JSON: %s. Raw: %s", parse_err, response_text)
        return {}, {}

    return parsed.get("tables", {}), parsed.get("columns", {})


def _build_schema_prompt_text(tables: Sequence[SchemaTable]) -> str:
    """Format tables and columns into a structured schema summary for LLM prompt."""
    schema_summary: list[str] = []
    for t in tables:
        cols_info: list[str] = []
        for c in t.columns:
            pk_flag = " (PRIMARY KEY)" if c.is_primary_key else ""
            fk_flag = f" (REFERENCES {c.fk_target_table}.{c.fk_target_column})" if c.is_foreign_key else ""
            cols_info.append(f"  - {c.column_name}: {c.data_type}{pk_flag}{fk_flag}")
        schema_summary.append(f"Table: {t.table_name}\n" + "\n".join(cols_info))
    return "\n\n".join(schema_summary)


def _prepare_columns_to_embed(
    tables: Sequence[SchemaTable],
    annotations: Sequence[SchemaAnnotation],
) -> list[tuple[SchemaColumn, SchemaTable, str]]:
    """Build composite embed text for each column, linking parent table and annotations."""
    table_annot_map: dict[uuid.UUID, list[SchemaAnnotation]] = {}
    col_annot_map: dict[uuid.UUID, list[SchemaAnnotation]] = {}
    for a in annotations:
        if a.schema_table_id:
            table_annot_map.setdefault(a.schema_table_id, []).append(a)
        if a.schema_column_id:
            col_annot_map.setdefault(a.schema_column_id, []).append(a)

    columns_to_embed: list[tuple[SchemaColumn, SchemaTable, str]] = []
    for table in tables:
        t_annots = table_annot_map.get(table.id, [])
        for col in table.columns:
            c_annots = col_annot_map.get(col.id, [])
            embed_text = build_composite_embed_text(
                column=col,
                table=table,
                table_annotations=t_annots,
                column_annotations=c_annots,
            )
            columns_to_embed.append((col, table, embed_text))
    return columns_to_embed


class EmbeddingService:
    """Domain service managing embedding generation, synchronization, and schema search."""

    def __init__(
        self,
        db: AsyncSession,
        connection_service: ConnectionService,
    ) -> None:
        self._db = db
        self._connection_service = connection_service
        self._repo = EmbeddingRepository(db)
        self._schema_repo = SchemaIntrospectionRepository(db)
        self._semantic_repo = SchemaAnnotationRepository(db)

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of texts in batches."""
        if not texts:
            return []

        embeddings_client = get_embeddings_client()
        batch_size = 50
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            try:
                vectors = embeddings_client.embed_documents(chunk)
                all_embeddings.extend(vectors)
            except Exception as exc:
                logger.exception("Embedding generation failed for chunk of %s texts: %s", len(chunk), exc)
                raise

        return all_embeddings

    async def generate_and_store_for_connection(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> int:
        """Fetch all introspected schema tables/columns and annotations, generate embeddings, and persist."""
        settings = get_settings()

        tables = await self._schema_repo.get_tables(
            project_id=project_id, connection_id=connection_id
        )
        if not tables:
            logger.info("No tables found for connection %s to embed", connection_id)
            return 0

        annotations = await self._semantic_repo.get_annotations_for_connection(
            project_id=project_id, connection_id=connection_id
        )
        columns_to_embed = _prepare_columns_to_embed(tables=tables, annotations=annotations)
        if not columns_to_embed:
            return 0

        texts = [item[2] for item in columns_to_embed]
        vectors = await self.generate_embeddings_batch(texts)

        records: list[dict[str, Any]] = [
            {
                "column_id": col.id,
                "embed_text": text,
                "embedding": vec,
                "model": settings.EMBEDDING_MODEL,
            }
            for (col, _tbl, text), vec in zip(columns_to_embed, vectors, strict=True)
        ]

        saved_count = await self._repo.bulk_save_embeddings(
            project_id=project_id,
            connection_id=connection_id,
            embeddings_data=records,
        )
        logger.info(
            "Successfully generated and stored %s embeddings for connection %s",
            saved_count,
            connection_id,
        )
        return saved_count

    async def generate_and_store_for_connection_stream(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        chunk_size: int = 5,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream real-time SSE progress while generating and saving schema embeddings."""
        settings = get_settings()

        tables = await self._schema_repo.get_tables(
            project_id=project_id, connection_id=connection_id
        )
        if not tables:
            yield {"event": "start", "total": 0, "tables_count": 0, "message": "No tables found to embed"}
            yield {"event": "complete", "total": 0, "model": settings.EMBEDDING_MODEL, "dimensions": settings.EMBEDDING_DIMENSIONS}
            return

        annotations = await self._semantic_repo.get_annotations_for_connection(
            project_id=project_id, connection_id=connection_id
        )
        columns_to_embed = _prepare_columns_to_embed(tables=tables, annotations=annotations)
        total_cols = len(columns_to_embed)

        yield {
            "event": "start",
            "total": total_cols,
            "tables_count": len(tables),
            "model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIMENSIONS,
            "message": f"Starting embedding generation for {total_cols} columns",
        }

        if total_cols == 0:
            yield {"event": "complete", "total": 0, "model": settings.EMBEDDING_MODEL, "dimensions": settings.EMBEDDING_DIMENSIONS}
            return

        completed_count = 0
        embeddings_client = get_embeddings_client()

        for i in range(0, total_cols, chunk_size):
            chunk = columns_to_embed[i : i + chunk_size]
            chunk_texts = [item[2] for item in chunk]

            try:
                vectors = embeddings_client.embed_documents(chunk_texts)
            except Exception as exc:
                logger.exception("Embedding generation failed during streaming: %s", exc)
                yield {"event": "error", "message": f"Failed to generate embeddings: {exc}"}
                return

            for (col, _tbl, text), vec in zip(chunk, vectors, strict=True):
                await self._repo.upsert_embedding(
                    project_id=project_id,
                    connection_id=connection_id,
                    column_id=col.id,
                    embed_text=text,
                    embedding=vec,
                    model=settings.EMBEDDING_MODEL,
                )

            completed_count += len(chunk)
            last_col, last_tbl, _ = chunk[-1]
            percentage = round((completed_count / total_cols) * 100, 1)

            yield {
                "event": "progress",
                "completed": completed_count,
                "total": total_cols,
                "current_table": last_tbl.table_name,
                "current_column": last_col.column_name,
                "percentage": percentage,
                "message": f"Processed {completed_count}/{total_cols} columns ({percentage}%)",
            }

        yield {
            "event": "complete",
            "total": total_cols,
            "model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIMENSIONS,
            "message": f"Successfully generated and stored {total_cols} embeddings",
        }

    async def regenerate_for_column(
        self,
        project_id: uuid.UUID,
        connection_id: uuid.UUID,
        column_id: uuid.UUID,
    ) -> None:
        """Regenerate embedding for a single column (e.g. after annotation change)."""
        settings = get_settings()

        # Fetch column details
        cache = await self._schema_repo.get_cache(
            project_id=project_id, connection_id=connection_id
        )
        if cache is None:
            return

        target_col: SchemaColumn | None = None
        target_table: SchemaTable | None = None
        for table in cache.tables:
            for col in table.columns:
                if col.id == column_id:
                    target_col = col
                    target_table = table
                    break
            if target_col is not None:
                break

        if target_col is None or target_table is None:
            return

        # Fetch annotations
        t_annots = await self._semantic_repo.get_annotations_for_table(
            project_id=project_id,
            connection_id=connection_id,
            schema_table_id=target_table.id,
        )
        col_annot = await self._semantic_repo.get_annotation_for_column(
            project_id=project_id,
            connection_id=connection_id,
            schema_column_id=column_id,
        )
        c_annots = [col_annot] if col_annot is not None else []

        embed_text = build_composite_embed_text(
            column=target_col,
            table=target_table,
            table_annotations=t_annots,
            column_annotations=c_annots,
        )

        vectors = await self.generate_embeddings_batch([embed_text])
        if vectors:
            await self._repo.upsert_embedding(
                project_id=project_id,
                connection_id=connection_id,
                column_id=column_id,
                embed_text=embed_text,
                embedding=vectors[0],
                model=settings.EMBEDDING_MODEL,
            )

    async def search_schema(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 10,
    ) -> list[SchemaSearchResult]:
        """Perform vector similarity search over introspected database schema."""
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )

        embeddings_client = get_embeddings_client()
        query_vector = embeddings_client.embed_query(query)

        raw_results = await self._repo.search_similar(
            project_id=project_id,
            connection_id=connection.id,
            query_embedding=query_vector,
            top_k=top_k,
        )

        return [SchemaSearchResult.model_validate(r) for r in raw_results]

    async def auto_suggest_descriptions(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AutoSuggestResponse:
        """Use configured LLM to generate draft business descriptions for schema tables and columns."""

        from langchain_core.messages import HumanMessage, SystemMessage


        settings = get_settings()
        connection = await self._connection_service.get_connection(
            project_id=project_id, user_id=user_id
        )

        # 1. Fetch tables with columns
        tables = await self._schema_repo.get_tables(
            project_id=project_id, connection_id=connection.id
        )
        if not tables:
            return AutoSuggestResponse(
                project_id=project_id,
                connection_id=connection.id,
                suggested_tables_count=0,
                suggested_columns_count=0,
                model=settings.LLM_MODEL,
            )

        # 2. Fetch existing annotations to avoid overwriting user edits
        existing_annots = await self._semantic_repo.get_annotations_for_connection(
            project_id=project_id, connection_id=connection.id
        )
        annotated_table_ids = {a.schema_table_id for a in existing_annots if a.schema_table_id}
        annotated_col_ids = {a.schema_column_id for a in existing_annots if a.schema_column_id}

        # 3. Build schema summary for LLM prompt
        prompt_schema_text = _build_schema_prompt_text(tables)

        system_msg = SystemMessage(
            content=(
                "You are an expert database architect and data analyst. "
                "Your task is to generate concise, clear, and business-friendly descriptions for database tables and columns. "
                "These descriptions help non-technical users understand data semantics. "
                "Respond ONLY with a valid JSON object matching this structure:\n"
                "{\n"
                '  "tables": {\n'
                '    "table_name": "Description of table purpose and entities stored"\n'
                "  },\n"
                '  "columns": {\n'
                '    "table_name.column_name": "Description of what this column represents"\n'
                "  }\n"
                "}"
            )
        )
        user_msg = HumanMessage(
            content=f"Here is the database schema:\n\n{prompt_schema_text}"
        )

        llm = get_llm_client(temperature=0.2)
        response = await llm.ainvoke([system_msg, user_msg])
        suggested_tables, suggested_columns = _parse_auto_suggest_json(str(response.content).strip())

        tables_count = 0
        columns_count = 0

        # Save table annotations
        for t in tables:
            if t.id not in annotated_table_ids and t.table_name in suggested_tables:
                note = str(suggested_tables[t.table_name]).strip()
                if note:
                    await self._semantic_repo.create_annotation(
                        project_id=project_id,
                        connection_id=connection.id,
                        target_type="table",
                        schema_table_id=t.id,
                        note=note,
                        is_auto_generated=True,
                    )
                    tables_count += 1

            # Save column annotations
            for c in t.columns:
                col_key = f"{t.table_name}.{c.column_name}"
                if c.id not in annotated_col_ids and (col_key in suggested_columns or c.column_name in suggested_columns):
                    col_note = str(suggested_columns.get(col_key) or suggested_columns.get(c.column_name)).strip()
                    if col_note:
                        await self._semantic_repo.create_annotation(
                            project_id=project_id,
                            connection_id=connection.id,
                            target_type="column",
                            schema_column_id=c.id,
                            note=col_note,
                            is_auto_generated=True,
                        )
                        columns_count += 1

        # Re-sync embeddings with new annotations
        if tables_count > 0 or columns_count > 0:
            await self.generate_and_store_for_connection(project_id, connection.id)

        return AutoSuggestResponse(
            project_id=project_id,
            connection_id=connection.id,
            suggested_tables_count=tables_count,
            suggested_columns_count=columns_count,
            model=settings.LLM_MODEL,
        )


def get_embedding_service(
    db: DbSession,
    connection_service: Annotated[ConnectionService, Depends(get_connection_service)],
) -> EmbeddingService:
    """FastAPI dependency provider for EmbeddingService."""
    return EmbeddingService(db=db, connection_service=connection_service)
