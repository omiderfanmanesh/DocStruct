"""LangChain-backed chat-model adapter helpers."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def _to_langchain_messages(messages: list[dict]) -> list[HumanMessage | AIMessage | SystemMessage]:
    converted: list[HumanMessage | AIMessage | SystemMessage] = []
    for message in messages:
        role = str(message.get("role", "user")).strip().lower()
        content = message.get("content", "")
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return str(content or "")


class LangChainChatAdapter:
    supports_structured_output = True

    @staticmethod
    def _to_langchain_messages(messages: list[dict]) -> list[HumanMessage | AIMessage | SystemMessage]:
        return _to_langchain_messages(messages)

    def _build_model(self, *, model: str, max_tokens: int):
        raise NotImplementedError

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        chat_model = self._build_model(model=model, max_tokens=max_tokens)
        response = chat_model.invoke(_to_langchain_messages(messages))
        return _coerce_text(response.content)

    def create_structured_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        schema: Any,
    ) -> Any:
        chat_model = self._build_model(model=model, max_tokens=max_tokens)
        structured_model = chat_model.with_structured_output(schema)
        return structured_model.invoke(_to_langchain_messages(messages))
