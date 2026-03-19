"""Anthropic Claude provider."""
from __future__ import annotations

import os
import sys


def build_anthropic_client():
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
        sys.exit(3)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(3)

    return anthropic.Anthropic(api_key=api_key)
