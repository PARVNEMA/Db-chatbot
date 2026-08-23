"""
Agent node — Guardrailed SQL execution (Phase 3).

Executes SQL via ConnectionManager with:
- Read-only enforcement
- Execution timeout
- Row limit cap
On error, signals the self-correction loop to retry SQL generation.
"""

# TODO: implement in Phase 3
