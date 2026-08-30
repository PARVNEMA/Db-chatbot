export interface IntrospectResponse {
  connection_id: string;
  project_id: string;
  table_count?: number;
  tables_count?: number;
  column_count?: number;
  columns_count?: number;
  introspected_at: string;
}

export interface TableSummary {
  id: string;
  table_name: string;
  schema_name: string | null;
  column_count?: number;
  columns_count?: number;
}

export interface SchemaOverviewResponse {
  project_id: string;
  connection_id: string;
  table_count?: number;
  tables_count?: number;
  column_count?: number;
  columns_count?: number;
  introspected_at: string;
  tables: TableSummary[];
}

export interface ColumnDetail {
  id: string;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  fk_target_table: string | null;
  fk_target_column: string | null;
  ordinal_position: number;
}

export interface TableDetailResponse {
  id: string;
  table_name: string;
  schema_name: string | null;
  columns: ColumnDetail[];
}
