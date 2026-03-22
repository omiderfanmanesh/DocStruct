"""LLM provider factory."""

from __future__ import annotations

import os
import sys

from docstruct.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from docstruct.infrastructure.llm.azure_adapter import AzureOpenAIAdapter


def build_client():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower().strip()
    if provider == "azure":
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
        try:
            return AzureOpenAIAdapter(
                api_key=api_key,
                endpoint=endpoint,
                deployment=deployment,
                api_version=api_version,
            )
        except ImportError:
            print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
            sys.exit(3)

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
            sys.exit(3)
        try:
            return AnthropicAdapter(api_key=api_key)
        except ImportError:
            print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
            sys.exit(3)

    print(f"ERROR: Unknown LLM_PROVIDER={provider!r}. Must be 'anthropic' or 'azure'.", file=sys.stderr)
    sys.exit(3)
