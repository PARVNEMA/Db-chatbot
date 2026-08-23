"""
Chat domain — service stub.

Will orchestrate:
- ChatSession CRUD.
- Invoking the LangGraph agent graph per message.
- SSE streaming of intermediate agent events (ADR-0003).
- Persisting ChatMessage rows after completion.
"""
# TODO: implement in Phase 4
