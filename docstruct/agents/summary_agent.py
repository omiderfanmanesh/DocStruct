"""SummaryAgent — generates a 2-3 sentence document summary via LLM."""
from __future__ import annotations


class SummaryAgent:
    """Generates a short document summary from the pre-TOC header and TOC text."""

    def __init__(self, client):
        self._client = client

    def run(self, pre_toc_text: str, toc_text: str) -> str:
        prompt = (
            "You are summarizing a legal/academic document.\n\n"
            "Based on the document header and table of contents below, write a concise summary "
            "of 2-3 sentences describing:\n"
            "1. What this document is (type, issuing body)\n"
            "2. Its main purpose or subject\n"
            "3. The key topics it covers\n\n"
            "Write in plain English. Be specific. Do not invent details not present in the text.\n\n"
            f"DOCUMENT HEADER:\n{pre_toc_text[:2000]}\n\n"
            f"TABLE OF CONTENTS:\n{toc_text[:2000]}"
        )
        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
