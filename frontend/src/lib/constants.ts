const normalizeApiUrl = (url: string): string => {
  const trimmed = url.trim().replace(/\/+$/, "");
  if (trimmed.endsWith("/api/v1")) {
    return trimmed;
  }
  if (trimmed.endsWith("/api")) {
    return `${trimmed}/v1`;
  }
  return `${trimmed}/api/v1`;
};

const getApiBaseUrl = (): string => {
  const envUrl =
    process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL;

  if (envUrl && envUrl.trim()) {
    // In production, an accidental localhost URL will fail from user browsers; fallback to relative /api/v1
    if (
      process.env.NODE_ENV === "production" &&
      (envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))
    ) {
      return "/api/v1";
    }
    return normalizeApiUrl(envUrl);
  }

  if (process.env.NODE_ENV === "production") {
    // In production without an explicit external backend URL, fallback to relative /api/v1
    return "/api/v1";
  }

  return "http://localhost:8000/api/v1";
};

export const API_BASE_URL = getApiBaseUrl();

export const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

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
