"""Anthropic implementation of the LLM port."""

from __future__ import annotations

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover
    ChatAnthropic = None

from docstruct.infrastructure.llm.langchain_adapter import LangChainChatAdapter


class AnthropicAdapter(LangChainChatAdapter):
    def __init__(self, api_key: str):
        if ChatAnthropic is None:
            raise ImportError("langchain-anthropic package not installed")
        self._api_key = api_key

    def _build_model(self, *, model: str, max_tokens: int):
        return ChatAnthropic(
            model=model,
            anthropic_api_key=self._api_key,
            max_tokens=max_tokens,
            temperature=0,
        )

