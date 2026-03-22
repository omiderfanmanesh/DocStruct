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
                        "Extract metadata from this document header. Return ONLY a JSON object with these keys:\n"
                        '  "title": the full document title (string)\n'
                        '  "year": academic year or date if present, else null\n'
                        '  "document_type": type of document, else null\n'
                        '  "organization": issuing organization or institution, else null\n'
                        '  "source": "explicit" if title is clearly stated as a heading, "inferred" if deduced from context\n\n'
                        f"DOCUMENT HEADER:\n{pre_toc_text[:2000]}"
                    ),
                }
            ],
        ).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        title = (data.get("title") or "").strip() or "Unknown"
        source = (data.get("source") or "").strip() or "inferred"
        year = (data.get("year") or "").strip() or None
        document_type = (data.get("document_type") or "").strip() or None
        organization = (data.get("organization") or "").strip() or None
        return DocumentMetadata(
            title=title,
            source=source,
            year=year,
            document_type=document_type,
            organization=organization,
        )
