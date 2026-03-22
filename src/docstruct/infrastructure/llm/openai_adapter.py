"""OpenAI implementation of the LLM port."""

from __future__ import annotations

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None

from docstruct.infrastructure.llm.langchain_adapter import LangChainChatAdapter


class OpenAIAdapter(LangChainChatAdapter):
    def __init__(self, *, api_key: str):
        if ChatOpenAI is None:
            raise ImportError("langchain-openai package not installed")
        self._api_key = api_key

    def _build_model(self, *, model: str, max_tokens: int):
        return ChatOpenAI(
            model=model,
            api_key=self._api_key,
            max_tokens=max_tokens,
            temperature=0,
        )

    def create_structured_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        schema,
    ):
        chat_model = self._build_model(model=model, max_tokens=max_tokens)
        structured_model = chat_model.with_structured_output(schema, method="function_calling")
        return structured_model.invoke(self._to_langchain_messages(messages))
