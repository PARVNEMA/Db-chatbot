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
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreate {
  name: string;
  dialect: string;
  connection_string: string;
}

export interface ConnectionUpdate {
  name?: string;
  dialect?: string;
  connection_string?: string;
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
