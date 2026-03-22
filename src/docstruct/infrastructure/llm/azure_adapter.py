"""Azure OpenAI implementation of the LLM port."""

from __future__ import annotations

try:
    from openai import AzureOpenAI
except ImportError:  # pragma: no cover
    AzureOpenAI = None


class AzureOpenAIAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
    ):
        if AzureOpenAI is None:
            raise ImportError("openai package not installed")
        self._deployment = deployment
        self._client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        del model
        response = self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""

