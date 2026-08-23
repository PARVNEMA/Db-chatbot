# 2. Dynamic Multi-Tenant Database Connection Manager

Date: 2026-08-23

## Status

Accepted

## Context

The platform allows users to connect arbitrary target relational databases (PostgreSQL, MySQL, SQL Server, Snowflake) to execute natural language queries. Target database connections must be isolated from the platform's metadata database, encrypted at rest, pooled efficiently, and executed with strict read-only security guardrails.

## Decision

We separate the **Platform Control Plane** (App Metadata DB storing projects, schema caches, and user chats via SQLAlchemy 2.0 + asyncpg) from the **Tenant Data Plane**.

We implement a dynamic `ConnectionManager` service that:
1. Decrypts connection strings stored in the `connections` table using Fernet symmetric encryption.
2. Manages pooled SQLAlchemy target engines dynamically per `project_id`.
3. Enforces execution guardrails: read-only sessions (`SET TRANSACTION READ ONLY` where supported), query execution timeouts (e.g. 10s), and maximum row limit caps (e.g. 1000 rows).

## Consequences

### Positive
- Strict security isolation between platform metadata and customer database connections.
- Protection against SQL injection and destructive queries (INSERT/UPDATE/DELETE/DROP).
- High performance through pooled engine reuse per project.

### Negative
- Dynamic engine pooling requires active lifecycle management (connection cleanup and pool sizing).
