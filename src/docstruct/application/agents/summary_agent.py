"""SummaryAgent: generate a short document summary via LLM."""

from __future__ import annotations

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig


class SummaryAgent:
    def __init__(self, client: LLMPort):
        self._client = client
        self._model = AgentConfig.from_env().model

    def run(self, pre_toc_text: str, toc_text: str) -> str:
        return self._client.create_message(
            model=self._model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are summarizing a legal/academic document.\n\n"
                        "Write a concise 2-3 sentence English summary using the header and TOC.\n\n"
                        f"DOCUMENT HEADER:\n{pre_toc_text[:2000]}\n\n"
                        f"TABLE OF CONTENTS:\n{toc_text[:2000]}"
                    ),
                }
            ],
        ).strip()

