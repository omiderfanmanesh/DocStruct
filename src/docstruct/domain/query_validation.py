"""Query validation, input sanitization, and prompt injection protection."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Maximum query length in characters (prevents token budget blowouts)
MAX_QUERY_LENGTH = 2000
MIN_QUERY_LENGTH = 3

# Patterns that suggest prompt injection attempts
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s*:\s*you", re.IGNORECASE),
    re.compile(r"\bDAN\b.*\bmode\b", re.IGNORECASE),
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"```\s*(system|assistant)\b", re.IGNORECASE),
]

# Characters that could be used for encoding-based injection
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


@dataclass
class QueryValidationResult:
    """Result of query validation."""

    is_valid: bool
    sanitized_query: str
    rejection_reason: str | None = None
    injection_detected: bool = False


def validate_query(question: str | None) -> QueryValidationResult:
    """Validate and sanitize a user query.

    Checks for:
    - None/empty/whitespace-only input
    - Length limits (too short or too long)
    - Control characters
    - Prompt injection patterns

    Returns:
        QueryValidationResult with sanitized query and any issues found.
    """
    if not question or not question.strip():
        return QueryValidationResult(
            is_valid=False,
            sanitized_query="",
            rejection_reason="Query is empty or contains only whitespace.",
        )

    # Strip control characters
    sanitized = _CONTROL_CHAR_RE.sub("", question)
    # Normalize whitespace
    sanitized = " ".join(sanitized.split()).strip()

    if len(sanitized) < MIN_QUERY_LENGTH:
        return QueryValidationResult(
            is_valid=False,
            sanitized_query=sanitized,
            rejection_reason=f"Query is too short (minimum {MIN_QUERY_LENGTH} characters).",
        )

    if len(sanitized) > MAX_QUERY_LENGTH:
        return QueryValidationResult(
            is_valid=False,
            sanitized_query=sanitized[:MAX_QUERY_LENGTH],
            rejection_reason=f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters.",
        )

    # Check for prompt injection
    injection_detected = _detect_prompt_injection(sanitized)

    if injection_detected:
        return QueryValidationResult(
            is_valid=False,
            sanitized_query=sanitized,
            rejection_reason="Query contains patterns that resemble prompt injection.",
            injection_detected=True,
        )

    return QueryValidationResult(
        is_valid=True,
        sanitized_query=sanitized,
    )


def _detect_prompt_injection(text: str) -> bool:
    """Check if the text contains known prompt injection patterns."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_for_llm_prompt(text: str, *, max_length: int = 2000) -> str:
    """Sanitize text before embedding it in an LLM prompt.

    Escapes special delimiters and truncates to prevent context overflow.
    """
    sanitized = _CONTROL_CHAR_RE.sub("", text)
    sanitized = " ".join(sanitized.split()).strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length - 3] + "..."
    return sanitized
