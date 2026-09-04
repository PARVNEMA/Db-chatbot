"""Agent domain — Deterministic unsafe-intent guardrail (pre-classification).

Provides fast, regex-based keyword detection to catch destructive database manipulation
intents before calling the LLM classifier or executing the SQL pipeline.
"""

from __future__ import annotations

import re

# Multi-word and context-sensitive patterns matching destructive SQL intent in natural language
_UNSAFE_INTENT_PATTERN = re.compile(
    r"\b("
    r"drop\s+(the\s+|a\s+|this\s+)?(table|database|schema|index|view|column|constraint|trigger|procedure|function|all)"
    r"|truncate\s+(the\s+)?(table\s+)?\w+"
    r"|truncate\b"
    r"|delete\s+(from|all|everything|every\s+row|the\s+entire|the\s+table)"
    r"|alter\s+(the\s+|a\s+|this\s+)?(table|database|schema|column)"
    r"|insert\s+into"
    r"|update\s+\w+\s+set"
    r"|create\s+(the\s+|a\s+)?(table|database|schema|index|view|trigger|procedure|function)"
    r"|grant\s+(all|select|insert|update|delete|drop|alter|execute)"
    r"|revoke\s+(all|select|insert|update|delete|drop|alter|execute)"
    r"|exec(ute)?\s+(sp_|xp_|sys\.)?\w+"
    r"|;\s*(drop|truncate|delete|alter|insert|update|create|grant|revoke)"
    r")\b",
    re.IGNORECASE,
)


def detect_unsafe_intent(user_query: str) -> str | None:
    """Check if a user query contains destructive/unsafe intent.

    Args:
        user_query: The natural language question or command submitted by the user.

    Returns:
        The matched keyword phrase if unsafe, or None if safe.
    """
    if not user_query or not user_query.strip():
        return None

    match = _UNSAFE_INTENT_PATTERN.search(user_query)
    return match.group(0).strip() if match else None
