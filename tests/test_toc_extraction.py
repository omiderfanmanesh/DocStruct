"""Tests for TOC extraction: classifier agent plus full extraction pipeline."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock

import pytest

from docstruct.application.agents.boundary_agent import BoundaryAgent
from docstruct.application.agents.classifier_agent import ClassifierAgent
from docstruct.application.extract_toc import extract_toc
from docstruct.domain.models import HeadingEntry


def classify_toc_entries(toc_text, client):
    return ClassifierAgent(client).run(toc_text)


def find_toc_boundaries(lines, client):
    boundary, _ = BoundaryAgent(client).run(lines)
    return boundary


GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def _make_mock_client(response_json: list[dict]):
    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps(response_json)
    return mock_client


def test_classify_toc_entries_returns_heading_entries():
    response = [
        {"title": "RECIPIENTS AND AMOUNTS", "kind": "section", "numbering": "SECTION I", "page": 10, "depth": 1, "confidence": 0.95},
        {"title": "COURSES AND UNIVERSITIES", "kind": "article", "numbering": "ART. 1", "page": 11, "depth": 2, "confidence": 0.98},
    ]
    client = _make_mock_client(response)
    entries = classify_toc_entries("# Summary\n# SECTION I. RECIPIENTS AND AMOUNTS 10\n# ART. 1 COURSES 11", client)

    assert len(entries) == 2
    assert all(isinstance(entry, HeadingEntry) for entry in entries)
    assert entries[0].kind == "section"
    assert entries[0].depth == 1
    assert entries[0].page == 10
    assert entries[1].kind == "article"
    assert entries[1].depth == 2


def test_classify_toc_entries_handles_markdown_fenced_response():
    response = [{"title": "Test", "kind": "article", "numbering": "Art. 1", "page": 5, "depth": 2, "confidence": 0.9}]
    mock_client = MagicMock()
    mock_client.create_message.return_value = "```json\n" + json.dumps(response) + "\n```"

    entries = classify_toc_entries("some toc text", mock_client)
    assert len(entries) == 1
    assert entries[0].title == "Test"


def _make_multi_call_client(
    boundary_response: dict,
    summary_text: str,
    metadata_dict: dict,
    boundary_chunks: int = 1,
):
    calls = [0]

    def side_effect(**kwargs):
        call_number = calls[0]
        calls[0] += 1
        if call_number < boundary_chunks:
            return json.dumps(boundary_response)
        if call_number == boundary_chunks:
            return summary_text
        return json.dumps(metadata_dict)

    client = MagicMock()
    client.create_message.side_effect = side_effect
    return client


def test_notice_toc_extraction(notice_md_path):
    golden = json.loads((GOLDEN_DIR / "notice_toc.json").read_text())
    mock_entries = [
        {"title": entry["title"], "kind": entry["kind"], "numbering": entry.get("numbering"), "page": entry.get("page"), "depth": entry["depth"], "confidence": 0.95}
        for entry in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 67, "toc_end": 575, "status": "done", "entries": mock_entries},
        summary_text="A notice of competition for scholarships and accommodation. Covers eligibility and application.",
        metadata_dict={"title": "Notice of competition a.y. 2025/26", "year": "2025/26", "document_type": "Notice of competition", "organization": "EDISU Piemonte", "source": "explicit"},
    )

    result = extract_toc(str(notice_md_path), client)
    assert result.toc_boundaries.start_line == 67
    assert result.toc_boundaries.end_line == 575
    assert len(result.toc) == len(golden)
    matches = sum(1 for actual, expected in zip(result.toc, golden) if actual.kind == expected["kind"] and actual.depth == expected["depth"])
    assert matches / len(golden) >= 0.95
    assert len(result.heading_map) > 0
    assert [entry for entry in result.heading_map if entry.kind == "section"]
    assert all(key in result.to_dict() for key in ["toc", "heading_map", "summary", "metadata", "toc_boundaries", "processing_log", "extracted_at"])


def test_disco_toc_extraction(disco_md_path):
    golden = json.loads((GOLDEN_DIR / "disco_toc.json").read_text())
    mock_entries = [
        {"title": entry["title"], "kind": entry["kind"], "numbering": entry.get("numbering"), "page": entry.get("page"), "depth": entry["depth"], "confidence": 0.95}
        for entry in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 34, "toc_end": 234, "status": "done", "entries": mock_entries},
        summary_text="A call for applications for right-to-study benefits. Covers scholarships, accommodation and services for eligible students.",
        metadata_dict={"title": "BANDO DiSCo", "source": "explicit", "year": "2025/26", "document_type": "Call for applications", "organization": "DiSCo"},
    )

    result = extract_toc(str(disco_md_path), client)
    assert result.toc_boundaries.marker == "(agent-detected)"
    assert len(result.toc) == len(golden)
    matches = sum(1 for actual, expected in zip(result.toc, golden) if actual.kind == expected["kind"] and actual.depth == expected["depth"])
    assert matches / len(golden) >= 0.95


def test_bologna_toc_extraction(bologna_md_path):
    golden = json.loads((GOLDEN_DIR / "bologna_toc.json").read_text())
    mock_entries = [
        {"title": entry["title"], "kind": entry["kind"], "numbering": entry.get("numbering"), "page": entry.get("page"), "depth": entry["depth"], "confidence": 0.9}
        for entry in golden
    ]
    client = _make_multi_call_client(
        boundary_response={"toc_start": 37, "toc_end": 523, "status": "done", "entries": mock_entries},
        summary_text="Un bando di concorso per borse di studio e servizi DSU. Copre requisiti economici e di merito per studenti universitari.",
        metadata_dict={"title": "Bando di concorso DSU", "source": "explicit", "year": "2025/26", "document_type": "Bando di concorso", "organization": "ER.GO"},
    )

    result = extract_toc(str(bologna_md_path), client)
    assert result.toc_boundaries.marker == "(agent-detected)"
    assert len(result.toc) == len(golden)
    matches = sum(1 for actual, expected in zip(result.toc, golden) if actual.kind == expected["kind"] and actual.depth == expected["depth"])
    assert matches / len(golden) >= 0.95


def _no_toc_client():
    client = MagicMock()
    client.create_message.return_value = json.dumps({"toc_start": -1, "toc_end": -1, "status": "searching"})
    return client


def test_no_toc_marker_raises_value_error(tmp_path):
    md = tmp_path / "no_toc.md"
    md.write_text("# Introduction\n\nSome body text without a TOC marker.\n")
    with pytest.raises(ValueError, match="No TOC section found"):
        extract_toc(str(md), _no_toc_client())


def test_empty_file_raises_value_error(tmp_path):
    md = tmp_path / "empty.md"
    md.write_text("")
    with pytest.raises(ValueError, match="No TOC section found"):
        extract_toc(str(md), _no_toc_client())


def test_llm_api_error_propagates(notice_md_path):
    class FakeAPIError(Exception):
        pass

    mock_client = MagicMock()
    mock_client.create_message.side_effect = FakeAPIError("API error")

    with pytest.raises(FakeAPIError):
        extract_toc(str(notice_md_path), mock_client)


def test_extract_toc_handles_string_entries_from_boundary_agent(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Summary\n\nGENERAL PROVISIONS\n")

    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            {
                "toc_start": 0,
                "toc_end": 2,
                "status": "done",
                "entries": ["GENERAL PROVISIONS"],
            }
        ),
        "A short summary.",
        json.dumps({"title": "General Provisions", "source": "inferred"}),
    ]

    result = extract_toc(str(md), client)

    assert len(result.toc) == 1
    assert result.toc[0].title == "GENERAL PROVISIONS"
    assert result.toc[0].kind == "topic"
