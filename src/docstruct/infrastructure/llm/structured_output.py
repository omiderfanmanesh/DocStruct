"""Structured-output helpers with graceful fallback for mocked clients."""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter


def _strip_code_fences(raw: str) -> str:
    stripped = raw.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_payload(raw: str) -> str:
    cleaned = _strip_code_fences(raw)
    object_start = cleaned.find("{")
    list_start = cleaned.find("[")
    starts = [start for start in [object_start, list_start] if start != -1]
    if not starts:
        return cleaned
    start = min(starts)
    object_end = cleaned.rfind("}")
    list_end = cleaned.rfind("]")
    end = max(object_end, list_end)
    if end >= start:
        return cleaned[start : end + 1]
    return cleaned[start:]


def invoke_structured(
    client,
    *,
    model: str,
    max_tokens: int,
    messages: list[dict],
    schema: Any,
) -> Any:
    if getattr(client, "supports_structured_output", False) is True:
        return client.create_structured_message(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            schema=schema,
        )

    raw = client.create_message(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    payload = json.loads(_extract_json_payload(raw))
    return TypeAdapter(schema).validate_python(payload)
