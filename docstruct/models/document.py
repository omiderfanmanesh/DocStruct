"""Document-level data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class HeadingEntry:
    title: str
    kind: Literal["section", "article", "subarticle", "annex", "topic"]
    depth: int
    numbering: str | None = None
    page: int | None = None
    confidence: float | None = None
    children: list[HeadingEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "depth": self.depth,
            "numbering": self.numbering,
            "page": self.page,
            "confidence": self.confidence,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> HeadingEntry:
        children = [cls.from_dict(c) for c in d.get("children", [])]
        return cls(
            title=d["title"],
            kind=d["kind"],
            depth=d["depth"],
            numbering=d.get("numbering"),
            page=d.get("page"),
            confidence=d.get("confidence"),
            children=children,
        )


@dataclass
class TOCBoundary:
    start_line: int
    end_line: int
    marker: str

    def to_dict(self) -> dict:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "marker": self.marker,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TOCBoundary:
        return cls(
            start_line=d["start_line"],
            end_line=d["end_line"],
            marker=d["marker"],
        )


@dataclass
class DocumentMetadata:
    title: str
    source: Literal["explicit", "inferred"]
    year: str | None = None
    document_type: str | None = None
    organization: str | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "year": self.year,
            "document_type": self.document_type,
            "organization": self.organization,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DocumentMetadata:
        return cls(
            title=d["title"],
            source=d["source"],
            year=d.get("year"),
            document_type=d.get("document_type"),
            organization=d.get("organization"),
        )
