"""Extraction result and log models."""
from __future__ import annotations

from dataclasses import dataclass

from docstruct.models.document import DocumentMetadata, HeadingEntry, TOCBoundary


@dataclass
class LogEntry:
    action: str
    detail: str
    line: int | None = None

    def to_dict(self) -> dict:
        return {"action": self.action, "detail": self.detail, "line": self.line}


@dataclass
class ExtractionResult:
    toc: list[HeadingEntry]
    heading_map: list[HeadingEntry]
    summary: str
    metadata: DocumentMetadata
    toc_boundaries: TOCBoundary
    processing_log: list[LogEntry]
    extracted_at: str

    def to_dict(self) -> dict:
        return {
            "toc": [e.to_dict() for e in self.toc],
            "heading_map": [e.to_dict() for e in self.heading_map],
            "summary": self.summary,
            "metadata": self.metadata.to_dict(),
            "toc_boundaries": self.toc_boundaries.to_dict(),
            "processing_log": [l.to_dict() for l in self.processing_log],
            "extracted_at": self.extracted_at,
        }
