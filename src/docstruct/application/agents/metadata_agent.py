"""MetadataAgent: extract structured document metadata via LLM."""

from __future__ import annotations

import json
import re

from docstruct.application.ports import LLMPort
from docstruct.domain.models import DocumentMetadata


class MetadataAgent:
    def __init__(self, client: LLMPort):
        self._client = client

    def run(self, pre_toc_text: str) -> DocumentMetadata:
        raw = self._client.create_message(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract metadata from this document header. Return only JSON with "
                        "title, year, document_type, organization, and source.\n\n"
                        f"DOCUMENT HEADER:\n{pre_toc_text[:2000]}"
                    ),
                }
            ],
        ).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        return DocumentMetadata(
            title=data.get("title", "Unknown"),
            source=data.get("source", "inferred"),
            year=data.get("year"),
            document_type=data.get("document_type"),
            organization=data.get("organization"),
        )

