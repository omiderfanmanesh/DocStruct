"""OpenAI implementation of the LLM port."""

from __future__ import annotations

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


class OpenAIAdapter:
    def __init__(self, *, api_key: str):
        if OpenAI is None:
            raise ImportError("openai package not installed")
        self._client = OpenAI(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""
