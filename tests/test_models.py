"""Unit tests for model serialization."""
from docstruct.domain.models import (
    DocumentMetadata,
    ExtractionResult,
    HeadingEntry,
    LogEntry,
    SearchAnswer,
    SearchDocumentIndex,
    SearchProfile,
    SearchTraceStep,
    TOCBoundary,
)


def test_heading_entry_round_trip():
    entry = HeadingEntry(
        title="General principles",
        kind="article",
        depth=2,
        numbering="Art. 1",
        pattern="Art. 1 - General principles",
        page=8,
        confidence=0.95,
    )
    assert HeadingEntry.from_dict(entry.to_dict()) == entry


def test_heading_entry_with_children_round_trip():
    child = HeadingEntry(title="Courses", kind="subarticle", depth=3, numbering="Art. 1(1)", page=11)
    parent = HeadingEntry(title="Recipients", kind="section", depth=1, numbering="SECTION I", page=10, children=[child])
    restored = HeadingEntry.from_dict(parent.to_dict())
    assert restored.title == parent.title
    assert len(restored.children) == 1
    assert restored.children[0].title == child.title


def test_toc_boundary_round_trip():
    b = TOCBoundary(start_line=10, end_line=50, marker="# TABLE OF CONTENTS")
    assert TOCBoundary.from_dict(b.to_dict()) == b


def test_document_metadata_round_trip():
    m = DocumentMetadata(
        title="Notice of competition",
        source="explicit",
        year="2025/26",
        document_type="Notice",
        organization="EDISU",
    )
    assert DocumentMetadata.from_dict(m.to_dict()) == m


def test_search_document_index_round_trip_with_scope_fields():
    index = SearchDocumentIndex(
        document_id="doc",
        title="Scholarship Notice",
        source_path="output/fixed/doc.md",
        summary="Deadlines and eligibility.",
        metadata=DocumentMetadata(title="Scholarship Notice", source="explicit", organization="EDISU"),
        doc_description="Call for applications",
        search_profile=SearchProfile(
            issuer="EDISU",
            region="Piedmont",
            covered_institutions=["University of Turin"],
            covered_cities=["Turin"],
            academic_year="2025/26",
            benefit_types=["scholarship", "accommodation"],
        ),
        scope_label="EDISU | Scholarship Notice",
        identity_terms=["EDISU", "Scholarship Notice"],
        structure=[{"node_id": "0001", "title": "Deadlines"}],
    )

    restored = SearchDocumentIndex.from_dict(index.to_dict())

    assert restored == index


def test_search_answer_to_dict_includes_guardrail_fields():
    answer = SearchAnswer(
        question="What are the deadlines?",
        answer="Which university do you mean?",
        document_ids=["doc"],
        needs_clarification=True,
        clarifying_question="Which university do you mean?",
        trace=[
            SearchTraceStep(
                stage="clarification_gate",
                message="Asked for clarification.",
                details={"options": ["EDISU Piemonte", "Venice"]},
            )
        ],
    )

    payload = answer.to_dict()

    assert payload["needs_clarification"] is True
    assert payload["clarifying_question"] == "Which university do you mean?"
    assert payload["trace"][0]["stage"] == "clarification_gate"


def test_extraction_result_to_dict_has_required_keys():
    result = ExtractionResult(
        toc=[HeadingEntry(title="T", kind="section", depth=1)],
        heading_map=[HeadingEntry(title="T", kind="section", depth=1)],
        summary="A test document.",
        metadata=DocumentMetadata(title="Test", source="inferred"),
        toc_boundaries=TOCBoundary(start_line=0, end_line=5, marker="# Summary"),
        processing_log=[LogEntry(action="detected", detail="marker found", line=0)],
        extracted_at="2026-03-06T00:00:00Z",
    )
    d = result.to_dict()
    assert set(d.keys()) == {"toc", "heading_map", "summary", "metadata", "toc_boundaries", "processing_log", "extracted_at"}
    assert isinstance(d["toc"], list)
    assert isinstance(d["heading_map"], list)
    assert isinstance(d["metadata"], dict)
    assert isinstance(d["toc_boundaries"], dict)
