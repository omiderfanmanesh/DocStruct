"""MetadataAgent: extract structured document metadata via LLM."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig
from docstruct.domain.models import DocumentMetadata
from docstruct.infrastructure.llm.structured_output import invoke_structured


class _MetadataPayload(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    year: Optional[str] = None
    document_type: Optional[str] = None
    organization: Optional[str] = None


class MetadataAgent:
    def __init__(self, client: LLMPort):
        self._client = client
        self._model = AgentConfig.from_env().model

    def run(self, pre_toc_text: str) -> DocumentMetadata:
        payload = invoke_structured(
            self._client,
            model=self._model,
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
            schema=_MetadataPayload,
        )
        title = (payload.title or "").strip() or "Unknown"
        source = (payload.source or "").strip() or "inferred"
        year = (payload.year or "").strip() or None
        document_type = (payload.document_type or "").strip() or None
        organization = (payload.organization or "").strip() or None
        return DocumentMetadata(
            title=title,
            source=source,
            year=year,
            document_type=document_type,
            organization=organization,
        )
