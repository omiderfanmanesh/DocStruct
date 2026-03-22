"""SummaryAgent: generate a short document summary via LLM."""

from __future__ import annotations

from docstruct.application.ports import LLMPort


class SummaryAgent:
    def __init__(self, client: LLMPort):
        self._client = client

    def run(self, pre_toc_text: str, toc_text: str) -> str:
        return self._client.create_message(
            model="claude-haiku-4-5-20251001",
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

