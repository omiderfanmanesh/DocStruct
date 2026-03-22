"""Anthropic implementation of the LLM port."""

from __future__ import annotations

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


class AnthropicAdapter:
    def __init__(self, api_key: str):
        if anthropic is None:
            raise ImportError("anthropic package not installed")
        self._client = anthropic.Anthropic(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.content[0].text

