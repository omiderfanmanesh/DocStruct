"""Azure OpenAI implementation of the LLM port."""

from __future__ import annotations

try:
    from langchain_openai import AzureChatOpenAI
except ImportError:  # pragma: no cover
    AzureChatOpenAI = None

from docstruct.infrastructure.llm.langchain_adapter import LangChainChatAdapter


class AzureOpenAIAdapter(LangChainChatAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
    ):
        if AzureChatOpenAI is None:
            raise ImportError("langchain-openai package not installed")
        self._api_key = api_key
        self._endpoint = endpoint
        self._deployment = deployment
        self._api_version = api_version

    def _build_model(self, *, model: str, max_tokens: int):
        return AzureChatOpenAI(
            api_key=self._api_key,
            azure_endpoint=self._endpoint,
            azure_deployment=self._deployment,
            api_version=self._api_version,
            model=model,
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

