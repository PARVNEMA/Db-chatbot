# 1. Modular Domain-Driven Architecture for FastAPI Backend

Date: 2026-08-23

## Status

Accepted

## Context

The platform requires multi-tenant data isolation, schema introspection, vector-based schema linking, and agentic natural language query execution. A standard layered MVC pattern (routers/services/models) risks tight coupling across features, making it hard for autonomous AI agents and developer teams to work safely on isolated capabilities.

## Decision

We adopt a **Modular Domain-Driven Layout** under `backend/app/domain/`. Each domain encapsulates its own API endpoints, Pydantic schemas, SQLAlchemy models, domain logic services, and repository layers:

- `app/domain/projects`
- `app/domain/connections`
- `app/domain/schema_introspection`
- `app/domain/semantic_layer`
- `app/domain/agent` (LangGraph graph, nodes, state)
- `app/domain/chat`

## Consequences

### Positive
- Strict boundaries between modules prevent accidental cross-domain dependencies.
- Subagents and AI coding agents can work in specific domain directories without breaking other components.
- Simplifies scaling each module into standalone services or embeddable chatbots in the future.

### Negative
- Slightly higher initial boilerplate setup compared to flat controller/service directories.
