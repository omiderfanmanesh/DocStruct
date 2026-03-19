"""Tests for TOC extraction — US1 (classify_toc_entries + full pipeline)."""
from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from docstruct.models import HeadingEntry
from docstruct.agents.classifier_agent import ClassifierAgent
from docstruct.agents.boundary_agent import BoundaryAgent
from docstruct.pipeline.extractor import extract_toc


def classify_toc_entries(toc_text, client):
    return ClassifierAgent(client).run(toc_text)


def find_toc_boundaries(lines, client):
    return BoundaryAgent(client).run(lines)

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


# ---------------------------------------------------------------------------
# T013 — Unit test: classify_toc_entries() with mocked Claude API
# ---------------------------------------------------------------------------

def _make_mock_client(response_json: list[dict]):
    """Build a mock anthropic.Anthropic client returning the given JSON."""
    mock_content = MagicMock()
    mock_content.text = json.dumps(response_json)

    mock_message = MagicMock()
    mock_message.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


def test_classify_toc_entries_returns_heading_entries():
    response = [
        {"title": "RECIPIENTS AND AMOUNTS", "kind": "section", "numbering": "SECTION I", "page": 10, "depth": 1, "confidence": 0.95},
        {"title": "COURSES AND UNIVERSITIES", "kind": "article", "numbering": "ART. 1", "page": 11, "depth": 2, "confidence": 0.98},
    ]
    client = _make_mock_client(response)
    entries = classify_toc_entries("# Summary\n# SECTION I. RECIPIENTS AND AMOUNTS 10\n# ART. 1 COURSES 11", client)

    assert len(entries) == 2
    assert all(isinstance(e, HeadingEntry) for e in entries)
    assert entries[0].kind == "section"
    assert entries[0].depth == 1
    assert entries[0].page == 10
    assert entries[1].kind == "article"
    assert entries[1].depth == 2


def test_classify_toc_entries_handles_markdown_fenced_response():
    response = [{"title": "Test", "kind": "article", "numbering": "Art. 1", "page": 5, "depth": 2, "confidence": 0.9}]
    mock_content = MagicMock()
    mock_content.text = "```json\n" + json.dumps(response) + "\n```"
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    entries = classify_toc_entries("some toc text", mock_client)
    assert len(entries) == 1
    assert entries[0].title == "Test"


# ---------------------------------------------------------------------------
# T014 — Golden integration test: Notice doc TOC extraction
# ---------------------------------------------------------------------------

def test_notice_toc_extraction(notice_md_path):
    """Full pipeline on Notice of competition doc — compare against golden fixture."""
    golden = json.loads((GOLDEN_DIR / "notice_toc.json").read_text())

    mock_response = [
        {"title": e["title"], "kind": e["kind"], "numbering": e.get("numbering"),
         "page": e.get("page"), "depth": e["depth"], "confidence": 0.95}
        for e in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 67, "toc_end": 575, "status": "done"},
        toc_response=mock_response,
        summary_text="A notice of competition for scholarships and accommodation. Covers eligibility and application.",
        metadata_dict={"title": "Notice of competition a.y. 2025/26", "year": "2025/26",
                       "document_type": "Notice of competition", "organization": "EDISU Piemonte", "source": "explicit"},
    )

    result = extract_toc(str(notice_md_path), client)

    # Validate boundaries
    assert result.toc_boundaries.start_line == 67
    assert result.toc_boundaries.end_line == 575

    # Validate TOC entries match golden (95%+ accuracy)
    assert len(result.toc) == len(golden)
    matches = sum(
        1 for r, g in zip(result.toc, golden)
        if r.kind == g["kind"] and r.depth == g["depth"]
    )
    accuracy = matches / len(golden)
    assert accuracy >= 0.95, f"TOC classification accuracy {accuracy:.0%} < 95% required"

    # Validate heading map is nested
    assert len(result.heading_map) > 0
    sections = [e for e in result.heading_map if e.kind == "section"]
    assert len(sections) >= 1

    # Validate output structure
    d = result.to_dict()
    assert all(k in d for k in ["toc", "heading_map", "summary", "metadata", "toc_boundaries", "processing_log", "extracted_at"])


# ---------------------------------------------------------------------------
# T027 — Golden integration test: DiSCo doc
# ---------------------------------------------------------------------------

def _make_multi_call_client(
    boundary_response: dict,
    toc_response: list,
    summary_text: str,
    metadata_dict: dict,
    boundary_chunks: int = 1,
):
    """Build a mock client for the full pipeline.

    Call order:
      1..boundary_chunks: boundary detection chunks (all return boundary_response)
      boundary_chunks+1:  classify_toc_entries  → toc_response (JSON list)
      boundary_chunks+2:  generate_summary      → summary_text
      boundary_chunks+3:  extract_metadata      → metadata_dict (JSON obj)
    """
    calls = [0]

    def side_effect(**kwargs):
        n = calls[0]
        calls[0] += 1
        msg = MagicMock()
        if n < boundary_chunks:
            c = MagicMock()
            c.text = json.dumps(boundary_response)
            msg.content = [c]
        elif n == boundary_chunks:
            c = MagicMock()
            c.text = json.dumps(toc_response)
            msg.content = [c]
        elif n == boundary_chunks + 1:
            c = MagicMock()
            c.text = summary_text
            msg.content = [c]
        else:
            c = MagicMock()
            c.text = json.dumps(metadata_dict)
            msg.content = [c]
        return msg

    client = MagicMock()
    client.messages.create.side_effect = side_effect
    return client


def test_disco_toc_extraction(disco_md_path):
    """Full pipeline on DiSCo BANDO doc — compare against golden fixture."""
    golden = json.loads((GOLDEN_DIR / "disco_toc.json").read_text())

    mock_response = [
        {"title": e["title"], "kind": e["kind"], "numbering": e.get("numbering"),
         "page": e.get("page"), "depth": e["depth"], "confidence": 0.95}
        for e in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 34, "toc_end": 234, "status": "done"},
        toc_response=mock_response,
        summary_text="A call for applications for right-to-study benefits. Covers scholarships, accommodation and services for eligible students.",
        metadata_dict={"title": "BANDO DiSCo", "source": "explicit", "year": "2025/26", "document_type": "Call for applications", "organization": "DiSCo"},
    )

    result = extract_toc(str(disco_md_path), client)

    assert result.toc_boundaries.marker == "(agent-detected)"
    assert len(result.toc) == len(golden)
    matches = sum(
        1 for r, g in zip(result.toc, golden)
        if r.kind == g["kind"] and r.depth == g["depth"]
    )
    assert matches / len(golden) >= 0.95


# ---------------------------------------------------------------------------
# T028 — Golden integration test: Bologna doc
# ---------------------------------------------------------------------------

def test_bologna_toc_extraction(bologna_md_path):
    """Full pipeline on Bologna bando-di-concorso doc — compare against golden fixture."""
    golden = json.loads((GOLDEN_DIR / "bologna_toc.json").read_text())

    mock_response = [
        {"title": e["title"], "kind": e["kind"], "numbering": e.get("numbering"),
         "page": e.get("page"), "depth": e["depth"], "confidence": 0.9}
        for e in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 37, "toc_end": 523, "status": "done"},
        toc_response=mock_response,
        summary_text="Un bando di concorso per borse di studio e servizi DSU. Copre requisiti economici e di merito per studenti universitari.",
        metadata_dict={"title": "Bando di concorso DSU", "source": "explicit", "year": "2025/26", "document_type": "Bando di concorso", "organization": "ER.GO"},
    )

    result = extract_toc(str(bologna_md_path), client)

    assert result.toc_boundaries.marker == "(agent-detected)"
    assert len(result.toc) == len(golden)
    matches = sum(
        1 for r, g in zip(result.toc, golden)
        if r.kind == g["kind"] and r.depth == g["depth"]
    )
    assert matches / len(golden) >= 0.95


# ---------------------------------------------------------------------------
# T029 — Edge case tests for find_toc_boundaries
# ---------------------------------------------------------------------------

def _no_toc_client():
    """Mock client that always tells the agent no TOC was found."""
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps({"toc_start": -1, "toc_end": -1, "status": "searching"}))]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def test_no_toc_marker_raises_value_error(tmp_path):
    """extract_toc on a file with no TOC marker raises ValueError (exit code 2)."""
    md = tmp_path / "no_toc.md"
    md.write_text("# Introduction\n\nSome body text without a TOC marker.\n")
    with pytest.raises(ValueError, match="No TOC section found"):
        extract_toc(str(md), _no_toc_client())


def test_empty_file_raises_value_error(tmp_path):
    """extract_toc on an empty file raises ValueError."""
    md = tmp_path / "empty.md"
    md.write_text("")
    with pytest.raises(ValueError, match="No TOC section found"):
        extract_toc(str(md), _no_toc_client())


# ---------------------------------------------------------------------------
# T030 — LLM API error handling
# ---------------------------------------------------------------------------

def test_llm_api_error_propagates(notice_md_path):
    """When Claude API raises, extract_toc should re-raise (CLI maps to exit code 3)."""
    class FakeAPIError(Exception):
        pass

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = FakeAPIError("API error")

    with pytest.raises(FakeAPIError):
        extract_toc(str(notice_md_path), mock_client)
