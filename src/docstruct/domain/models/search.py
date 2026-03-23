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
class SearchProfile:
    issuer: str | None = None
    region: str | None = None
    covered_institutions: list[str] = field(default_factory=list)
    covered_cities: list[str] = field(default_factory=list)
    academic_year: str | None = None
    benefit_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "region": self.region,
            "covered_institutions": self.covered_institutions,
            "covered_cities": self.covered_cities,
            "academic_year": self.academic_year,
            "benefit_types": self.benefit_types,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SearchProfile | None":
        if not data:
            return None
        return cls(
            issuer=data.get("issuer"),
            region=data.get("region"),
            covered_institutions=list(data.get("covered_institutions", [])),
            covered_cities=list(data.get("covered_cities", [])),
            academic_year=data.get("academic_year"),
            benefit_types=list(data.get("benefit_types", [])),
        )


@dataclass
class SearchDocumentIndex:
    document_id: str
    title: str
    source_path: str
    summary: str | None = None
    metadata: DocumentMetadata | None = None
    doc_description: str | None = None
    search_profile: SearchProfile | None = None
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
            "search_profile": self.search_profile.to_dict() if self.search_profile else None,
            "scope_label": self.scope_label,
            "identity_terms": self.identity_terms,
            "structure": self.structure,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchDocumentIndex":
        metadata = data.get("metadata")
        search_profile = data.get("search_profile")
        return cls(
            document_id=data["document_id"],
            title=data["title"],
            source_path=data["source_path"],
            summary=data.get("summary"),
            metadata=DocumentMetadata.from_dict(metadata) if metadata else None,
            doc_description=data.get("doc_description"),
            search_profile=SearchProfile.from_dict(search_profile),
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
class SearchTraceStep:
    stage: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchTraceStep":
        return cls(
            stage=data["stage"],
            message=data["message"],
            details=dict(data.get("details", {})),
        )


@dataclass
class SearchAnswer:
    question: str
    answer: str
    citations: list[SearchCitation] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    retrieval_notes: str | None = None
    needs_clarification: bool = False
    clarifying_question: str | None = None
    trace: list[SearchTraceStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [citation.to_dict() for citation in self.citations],
            "document_ids": self.document_ids,
            "retrieval_notes": self.retrieval_notes,
            "needs_clarification": self.needs_clarification,
            "clarifying_question": self.clarifying_question,
            "trace": [step.to_dict() for step in self.trace],
        }


@dataclass
class RetrievalCandidate:
    """A document or section candidate returned by the retrieval layer (before LLM ranking)."""

    document_id: str
    node_id: str | None  # None for document-level candidates; set for section nodes
    node_type: str  # "document" or "section"
    graph_rank: int | None = None  # Rank from graph matching (1-based), None if not returned
    fulltext_rank: int | None = None  # Rank from full-text search
    vector_rank: int | None = None  # Rank from vector similarity search
    rrf_score: float = 0.0  # Fused RRF score
    source_node: dict[str, Any] = field(default_factory=dict)  # Raw Neo4j node properties for context


@dataclass
class EmbeddingPayload:
    """Enriched text input for section embedding generation."""

    node_id: str  # Target section node ID
    document_id: str  # Parent document ID
    text: str  # Enriched text: section content + document context
    provider: str  # "openai" or "cohere"
    model: str  # Model identifier (e.g., "text-embedding-3-small")
