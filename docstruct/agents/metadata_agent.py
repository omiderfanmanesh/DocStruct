"""MetadataAgent — extracts structured document metadata via LLM."""
from __future__ import annotations

import json
import re

from docstruct.models.document import DocumentMetadata


class MetadataAgent:
    """Extracts title, year, document type, and organization from the header section."""

    def __init__(self, client):
        self._client = client

    def run(self, pre_toc_text: str) -> DocumentMetadata:
        prompt = (
            "Extract metadata from this document header. Return ONLY a JSON object with these keys:\n"
            '  "title": the full document title (string)\n'
            '  "year": academic year or date if present (string, e.g. "2025/26"), else null\n'
            '  "document_type": type of document (e.g. "Notice of competition", "Call for applications", "Bando di concorso"), else null\n'
            '  "organization": issuing organization/institution name, else null\n'
            '  "source": "explicit" if title is clearly stated as a heading, "inferred" if deduced from context\n\n'
            "Return ONLY the JSON object, no explanation.\n\n"
            f"DOCUMENT HEADER:\n{pre_toc_text[:2000]}"
        )
        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
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
