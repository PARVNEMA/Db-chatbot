export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const APP_NAME =
  process.env.NEXT_PUBLIC_APP_NAME || "NL-DB Query Platform";

export const TOKEN_STORAGE_KEY = "access_token";

export const SUPPORTED_DIALECTS = [
  { value: "postgresql", label: "PostgreSQL", defaultPort: 5432 },
  { value: "mysql", label: "MySQL", defaultPort: 3306 },
  { value: "mssql", label: "SQL Server (MSSQL)", defaultPort: 1433 },
  { value: "snowflake", label: "Snowflake", defaultPort: 443 },
  { value: "sqlite", label: "SQLite", defaultPort: null },
] as const;
