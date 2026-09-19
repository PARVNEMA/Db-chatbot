export type SupportedDialect =
  | "postgresql"
  | "mysql"
  | "mssql"
  | "snowflake"
  | "sqlite";

export interface Connection {
  id: string;
  project_id: string;
  name: string;
  dialect: SupportedDialect | string;
  writes_enabled?: boolean;
  max_insert_rows_per_table?: number;
  max_patch_rows_per_table?: number;
  max_total_rows_per_changeset?: number;
  max_tables_per_changeset?: number;
  approval_timeout_minutes?: number;
  undo_window_minutes?: number;
  blocked_tables?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreate {
  name: string;
  dialect: string;
  connection_string: string;
  writes_enabled?: boolean;
  max_insert_rows_per_table?: number;
  max_patch_rows_per_table?: number;
  max_total_rows_per_changeset?: number;
  max_tables_per_changeset?: number;
  approval_timeout_minutes?: number;
  undo_window_minutes?: number;
  blocked_tables?: string[];
}

export interface ConnectionUpdate {
  name?: string;
  dialect?: string;
  connection_string?: string;
  writes_enabled?: boolean;
  max_insert_rows_per_table?: number;
  max_patch_rows_per_table?: number;
  max_total_rows_per_changeset?: number;
  max_tables_per_changeset?: number;
  approval_timeout_minutes?: number;
  undo_window_minutes?: number;
  blocked_tables?: string[];
}

export interface ConnectionTestRequest {
  connection_string?: string;
  dialect?: string;
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  dialect: string;
  latency_ms: number | null;
}
