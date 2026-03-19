"""Azure OpenAI provider — wraps AzureOpenAI to match the Anthropic client interface."""
from __future__ import annotations

import os
import sys


def build_azure_client():
    try:
        from openai import AzureOpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(3)

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if not api_key:
        print("ERROR: AZURE_OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(3)
    if not endpoint:
        print("ERROR: AZURE_OPENAI_ENDPOINT not set.", file=sys.stderr)
        sys.exit(3)

    raw = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)
    return _AzureClientWrapper(raw, deployment)


class _AzureClientWrapper:
    """Presents the same interface as anthropic.Anthropic for the pipeline."""

    def __init__(self, azure_client, deployment: str):
        self._client = azure_client
        self._deployment = deployment
        self.messages = _MessagesNamespace(azure_client, deployment)


class _MessagesNamespace:
    def __init__(self, azure_client, deployment: str):
        self._client = azure_client
        self._deployment = deployment

    def create(self, *, model: str, max_tokens: int, messages: list) -> "_AzureResponse":
        response = self._client.chat.completions.create(
            model=self._deployment,
            max_tokens=max_tokens,
            messages=messages,
        )
        return _AzureResponse(response)


class _AzureResponse:
    def __init__(self, openai_response):
        text = openai_response.choices[0].message.content or ""
        self.content = [_TextContent(text)]


class _TextContent:
    def __init__(self, text: str):
        self.text = text
