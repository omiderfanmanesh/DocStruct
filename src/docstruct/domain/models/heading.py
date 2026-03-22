"""Heading-oriented domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class HeadingEntry:
    title: str
    kind: Literal["section", "article", "subarticle", "annex", "topic"]
    depth: int
    numbering: str | None = None
    separator: str | None = None
    pattern: str | None = None
    page: int | None = None
    confidence: float | None = None
    children: list["HeadingEntry"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "depth": self.depth,
            "numbering": self.numbering,
            "separator": self.separator,
            "pattern": self.pattern,
            "page": self.page,
            "confidence": self.confidence,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HeadingEntry":
        return cls(
            title=data["title"],
            kind=data["kind"],
            depth=data["depth"],
            numbering=data.get("numbering"),
            separator=data.get("separator"),
            pattern=data.get("pattern"),
            page=data.get("page"),
            confidence=data.get("confidence"),
            children=[cls.from_dict(child) for child in data.get("children", [])],
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
    def from_dict(cls, data: dict) -> "TOCBoundary":
        return cls(
            start_line=data["start_line"],
            end_line=data["end_line"],
            marker=data["marker"],
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
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        return cls(
            title=data["title"],
            source=data["source"],
            year=data.get("year"),
            document_type=data.get("document_type"),
            organization=data.get("organization"),
        )
