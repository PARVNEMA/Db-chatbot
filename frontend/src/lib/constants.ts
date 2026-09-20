const getApiBaseUrl = (): string => {
  const envUrl =
    process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL;

  if (process.env.NODE_ENV === "production") {
    // In production, localhost will fail from user browsers; fallback to relative /api/v1
    if (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1")) {
      return "/api/v1";
    }
    const trimmed = envUrl.replace(/\/+$/, "");
    if (!trimmed.endsWith("/api/v1")) {
      return trimmed.endsWith("/api") ? `${trimmed}/v1` : `${trimmed}/api/v1`;
    }
    return trimmed;
  }

  return envUrl || "http://localhost:8000/api/v1";
};

export const API_BASE_URL = getApiBaseUrl();

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
