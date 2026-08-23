# 3. LangGraph Execution with SSE Streaming and State Checkpointing

Date: 2026-08-23

## Status

Accepted

## Context

Natural language query translation involves multiple reasoning steps (intent classification, schema vector retrieval, SQL generation, guardrailed execution, self-correction, and NL formatting). Users require real-time feedback during long-running agent workflows and state persistence for multi-turn follow-up queries.

## Decision

We use **LangGraph** for workflow orchestration, combined with:
1. **Server-Sent Events (SSE)** via FastAPI's `EventSourceResponse` to stream intermediate graph state events to the Next.js frontend in real time.
2. **`AsyncPostgresSaver`** checkpointer to persist LangGraph state per `(project_id, session_id)` pair in PostgreSQL.

## Consequences

### Positive
- Enhanced UX with step-by-step agent progress updates in the UI.
- Seamless multi-turn conversation memory with state persistence across HTTP requests.

### Negative
- Client connections must maintain persistent HTTP connections for streaming.
