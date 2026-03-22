"""Search-oriented domain entities for PageIndex-backed document QA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docstruct.domain.models.heading import DocumentMetadata


@dataclass
class SearchCitation:
    document_id: str
    document_title: str
    node_id: str
    node_title: str
    line_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "node_id": self.node_id,
            "node_title": self.node_title,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchCitation":
        return cls(
            document_id=data["document_id"],
            document_title=data["document_title"],
            node_id=data["node_id"],
            node_title=data["node_title"],
            line_number=data.get("line_number"),
        )


@dataclass
class SearchDocumentIndex:
    document_id: str
    title: str
    source_path: str
    summary: str | None = None
    metadata: DocumentMetadata | None = None
    doc_description: str | None = None
    scope_label: str | None = None
    identity_terms: list[str] = field(default_factory=list)
    structure: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "source_path": self.source_path,
            "summary": self.summary,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "doc_description": self.doc_description,
            "scope_label": self.scope_label,
            "identity_terms": self.identity_terms,
            "structure": self.structure,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchDocumentIndex":
        metadata = data.get("metadata")
        return cls(
            document_id=data["document_id"],
            title=data["title"],
            source_path=data["source_path"],
            summary=data.get("summary"),
            metadata=DocumentMetadata.from_dict(metadata) if metadata else None,
            doc_description=data.get("doc_description"),
            scope_label=data.get("scope_label"),
            identity_terms=list(data.get("identity_terms", [])),
            structure=list(data.get("structure", [])),
        )


@dataclass
class SearchSelectionDecision:
    document_ids: list[str] = field(default_factory=list)
    thinking: str | None = None
    needs_clarification: bool = False
    clarifying_question: str | None = None


@dataclass
class SearchAnswer:
    question: str
    answer: str
    citations: list[SearchCitation] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    retrieval_notes: str | None = None
    needs_clarification: bool = False
    clarifying_question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [citation.to_dict() for citation in self.citations],
            "document_ids": self.document_ids,
            "retrieval_notes": self.retrieval_notes,
            "needs_clarification": self.needs_clarification,
            "clarifying_question": self.clarifying_question,
        }
