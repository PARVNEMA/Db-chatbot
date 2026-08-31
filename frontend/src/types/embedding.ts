export interface SchemaSearchRequest {
  query: string;
  top_k?: number;
}

export interface SchemaSearchResult {
  column_id: string;
  table_name: string;
  schema_name: string | null;
  column_name: string;
  data_type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  fk_target_table: string | null;
  fk_target_column: string | null;
  embed_text: string;
  similarity_score: number;
}

export interface EmbeddingGenerateResponse {
  project_id: string;
  connection_id: string;
  embedded_columns_count: number;
  model: string;
  dimensions: number;
}

export interface AutoSuggestRequest {
  table_id: string;
}

export interface AutoSuggestResponse {
  project_id: string;
  connection_id: string;
  table_id: string;
  table_name: string;
  table_description?: string | null;
  column_descriptions?: Record<string, string>;
  suggested_tables_count: number;
  suggested_columns_count: number;
  model: string;
}

export interface EmbeddingSSEEvent {
  event:
    | "start"
    | "progress"
    | "table_start"
    | "column_embedded"
    | "batch_complete"
    | "complete"
    | "error";
  table_name?: string;
  column_name?: string;
  columns_processed?: number;
  total_columns?: number;
  progress_percent?: number;
  message?: string;
  error?: string;
}
