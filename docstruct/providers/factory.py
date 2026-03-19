"""LLM provider factory — reads LLM_PROVIDER from environment."""
from __future__ import annotations

import os
import sys


def build_client():
    """Return a client for the configured LLM provider.

    Supported values for LLM_PROVIDER:
      - "anthropic" (default): uses ANTHROPIC_API_KEY
      - "azure": uses AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
                 AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower().strip()
    if provider == "azure":
        from docstruct.providers.azure import build_azure_client
        return build_azure_client()
    elif provider == "anthropic":
        from docstruct.providers.anthropic import build_anthropic_client
        return build_anthropic_client()
    else:
        print(f"ERROR: Unknown LLM_PROVIDER={provider!r}. Must be 'anthropic' or 'azure'.", file=sys.stderr)
        sys.exit(3)
