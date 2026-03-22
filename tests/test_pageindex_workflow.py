"""Tests for PageIndex-backed indexing and document QA workflow."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from docstruct.application.pageindex_workflow import (
    answer_question,
    build_search_index,
    load_search_indexes,
)


def test_build_search_index_persists_pageindex_document(tmp_path):
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text("# Title\n\n## Deadlines\n\nSubmit by April 1.\n", encoding="utf-8")

    toc_path = tmp_path / "doc.json"
    toc_path.write_text(
        json.dumps(
            {
                "summary": "Scholarship notice with deadlines.",
                "metadata": {
                    "title": "Scholarship Notice",
                    "source": "explicit",
                    "year": "2025/26",
                    "document_type": "Notice",
                    "organization": "EDISU",
                },
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "doc.pageindex.json"
    with patch(
        "docstruct.application.pageindex_workflow.build_markdown_tree",
        return_value={
            "doc_name": "doc",
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "0001",
                    "line_num": 3,
                    "text": "Submit by April 1.",
                    "nodes": [],
                }
            ],
        },
    ):
        index = build_search_index(str(markdown_path), str(output_path), extraction_json_path=str(toc_path))

    assert index.title == "Scholarship Notice"
    assert index.summary == "Scholarship notice with deadlines."
    assert output_path.exists()

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["document_id"] == "doc"
    assert loaded["search_profile"]["issuer"] == "EDISU"
    assert loaded["search_profile"]["academic_year"] == "2025/26"
    assert loaded["search_profile"]["benefit_types"] == ["scholarship"]
    assert loaded["scope_label"] == "EDISU | Scholarship Notice | 2025/26"
    assert "EDISU" in loaded["identity_terms"]
    assert loaded["structure"][0]["node_id"] == "0001"


def test_load_search_indexes_reads_written_indexes(tmp_path):
    index_path = tmp_path / "doc.pageindex.json"
    index_path.write_text(
        json.dumps(
            {
                "document_id": "doc",
                "title": "Scholarship Notice",
                "source_path": "output/fixed/doc.md",
                "summary": "Deadlines and eligibility.",
                "metadata": {
                    "title": "Scholarship Notice",
                    "source": "explicit",
                    "year": "2025/26",
                    "document_type": "Notice",
                    "organization": "EDISU",
                },
                "doc_description": None,
                "structure": [],
            }
        ),
        encoding="utf-8",
    )

    indexes = load_search_indexes(str(tmp_path))

    assert len(indexes) == 1
    assert indexes[0].document_id == "doc"
    assert indexes[0].metadata is not None
    assert indexes[0].metadata.organization == "EDISU"
    assert indexes[0].search_profile is None
    assert indexes[0].scope_label is None


def test_build_search_index_falls_back_from_unknown_title_and_extracts_search_profile(tmp_path):
    markdown_path = tmp_path / "campania.md"
    markdown_path.write_text(
        "# ARTICLE 1\n\n## Eligible students\n\nStudents enrolled at the University of Naples and the University of Salerno may apply.\n",
        encoding="utf-8",
    )

    toc_path = tmp_path / "campania.json"
    toc_path.write_text(
        json.dumps(
            {
                "summary": "The document is a call for applications issued by A.Di.S.U.R.C. for scholarships, accommodation places, and international mobility grants for the 2025/2026 academic year. It aims to support university students in the Campania region.",
                "metadata": {
                    "title": "Unknown",
                    "source": "inferred",
                    "year": None,
                    "document_type": None,
                    "organization": None,
                },
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "campania.pageindex.json"
    with patch(
        "docstruct.application.pageindex_workflow.build_markdown_tree",
        return_value={
            "doc_name": "campania",
            "structure": [
                {
                    "title": "Eligible students",
                    "node_id": "0001",
                    "line_num": 3,
                    "text": "Students enrolled at the University of Naples and the University of Salerno may apply.",
                    "nodes": [],
                }
            ],
        },
    ):
        index = build_search_index(str(markdown_path), str(output_path), extraction_json_path=str(toc_path))

    assert index.title == "campania"
    assert index.search_profile is not None
    assert index.search_profile.issuer == "A.Di.S.U.R.C"
    assert index.search_profile.region == "Campania"
    assert index.search_profile.academic_year == "2025/2026"
    assert "University of Naples" in index.search_profile.covered_institutions
    assert "University of Salerno" in index.search_profile.covered_institutions


def test_build_search_index_extracts_region_and_institutions_from_scope_nodes(tmp_path):
    markdown_path = tmp_path / "piemonte.md"
    markdown_path.write_text("# Scope\n", encoding="utf-8")

    toc_path = tmp_path / "piemonte.json"
    toc_path.write_text(
        json.dumps(
            {
                "summary": "Scholarship notice with deadlines and eligibility for the academic year 2025/26.",
                "metadata": {
                    "title": "Unknown",
                    "source": "inferred",
                    "year": "2025/26",
                    "document_type": "Notice",
                    "organization": None,
                },
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "piemonte.pageindex.json"
    with patch(
        "docstruct.application.pageindex_workflow.build_markdown_tree",
        return_value={
            "doc_name": "piemonte",
            "structure": [
                {
                    "title": "Universities",
                    "node_id": "0001",
                    "line_num": 3,
                    "text": (
                        "Students enrolled in Piedmont Universities may apply. "
                        "For the academic year 2025/26 students enrolled at the University of Turin, "
                        "Turin Polytechnic, and University of Eastern Piedmont may apply."
                    ),
                    "nodes": [],
                }
            ],
        },
    ):
        index = build_search_index(str(markdown_path), str(output_path), extraction_json_path=str(toc_path))

    assert index.search_profile is not None
    assert index.search_profile.region == "Piedmont"
    assert "University of Turin" in index.search_profile.covered_institutions
    assert "Turin Polytechnic" in index.search_profile.covered_institutions


def test_answer_question_uses_agentic_document_and_node_selection(tmp_path):
    docs = [
        {
            "document_id": "notice",
            "title": "Scholarship Notice",
            "source_path": "output/fixed/notice.md",
            "summary": "Contains application deadlines and eligibility.",
            "metadata": {
                "title": "Scholarship Notice",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "EDISU",
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "0001",
                    "line_num": 18,
                    "text": "Applications close on April 1.",
                    "nodes": [],
                }
            ],
        },
        {
            "document_id": "housing",
            "title": "Housing Rules",
            "source_path": "output/fixed/housing.md",
            "summary": "Contains accommodation policies.",
            "metadata": {
                "title": "Housing Rules",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Rules",
                "organization": "EDISU",
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Rooms",
                    "node_id": "1001",
                    "line_num": 12,
                    "text": "Accommodation allocation rules.",
                    "nodes": [],
                }
            ],
        },
    ]
    for payload in docs:
        path = tmp_path / f"{payload['document_id']}.pageindex.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            {
                "rewritten_question": "When is the application deadline?",
                "reasoning": "The original question is already specific enough for retrieval.",
                "inferred_document_ids": ["notice"],
            }
        ),
        json.dumps({"thinking": "The notice mentions deadlines.", "document_ids": ["notice"]}),
        json.dumps({"thinking": "The Deadlines node is directly relevant.", "node_ids": ["0001"]}),
        json.dumps(
            {
                "answer": "The application deadline is April 1.",
                "citations": [
                    {
                        "document_id": "notice",
                        "document_title": "Scholarship Notice",
                        "node_id": "0001",
                        "node_title": "Deadlines",
                        "line_number": 18,
                    }
                ],
            }
        ),
    ]

    result = answer_question("When is the application deadline?", str(tmp_path), client)

    assert result.answer == "The application deadline is April 1."
    assert result.document_ids == ["notice"]
    assert len(result.citations) == 1
    assert result.citations[0].node_title == "Deadlines"
    assert [step.stage for step in result.trace[:4]] == [
        "load_indexes",
        "intent_detection",
        "initial_ranking",
        "rewrite_question",
    ]


def test_answer_question_returns_clarification_for_ambiguous_documents(tmp_path):
    docs = [
        {
            "document_id": "venice",
            "title": "Scholarship Call",
            "source_path": "output/fixed/venice.md",
            "summary": "Contains application deadlines for students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "Ca' Foscari University of Venice",
            },
            "scope_label": "Ca' Foscari University of Venice | Scholarship Call | 2025/26",
            "identity_terms": ["Ca' Foscari University of Venice", "Scholarship Call", "2025/26"],
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "0001",
                    "line_num": 18,
                    "text": "Applications close on October 31.",
                    "nodes": [],
                }
            ],
        },
        {
            "document_id": "piemonte",
            "title": "Scholarship Call",
            "source_path": "output/fixed/piemonte.md",
            "summary": "Contains application deadlines for students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "EDISU Piemonte",
            },
            "scope_label": "EDISU Piemonte | Scholarship Call | 2025/26",
            "identity_terms": ["EDISU Piemonte", "Scholarship Call", "2025/26"],
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "1001",
                    "line_num": 24,
                    "text": "Applications close on September 9.",
                    "nodes": [],
                }
            ],
        },
    ]
    for payload in docs:
        path = tmp_path / f"{payload['document_id']}.pageindex.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    client = MagicMock()

    result = answer_question("What are the application deadlines?", str(tmp_path), client)

    assert result.needs_clarification is True
    assert result.document_ids == []
    assert "Please specify the university, region, or issuing organization" in result.answer
    assert "EDISU Piemonte" in (result.clarifying_question or "")
    assert client.create_message.call_count == 0
    assert result.trace[-1].stage == "clarification_gate"


def test_answer_question_keeps_guardrail_when_synthesis_detects_scope_conflict(tmp_path):
    docs = [
        {
            "document_id": "venice",
            "title": "Scholarship Call",
            "source_path": "output/fixed/venice.md",
            "summary": "Contains application deadlines for students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "Ca' Foscari University of Venice",
            },
            "scope_label": "Ca' Foscari University of Venice | Scholarship Call | 2025/26",
            "identity_terms": ["Ca' Foscari University of Venice", "Scholarship Call", "2025/26"],
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "0001",
                    "line_num": 18,
                    "text": "Applications close on October 31.",
                    "nodes": [],
                }
            ],
        },
        {
            "document_id": "piemonte",
            "title": "Scholarship Call",
            "source_path": "output/fixed/piemonte.md",
            "summary": "Contains application deadlines for students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "EDISU Piemonte",
            },
            "scope_label": "EDISU Piemonte | Scholarship Call | 2025/26",
            "identity_terms": ["EDISU Piemonte", "Scholarship Call", "2025/26"],
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "1001",
                    "line_num": 24,
                    "text": "Applications close on September 9.",
                    "nodes": [],
                }
            ],
        },
    ]
    for payload in docs:
        path = tmp_path / f"{payload['document_id']}.pageindex.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            {
                "rewritten_question": "For Ca' Foscari University of Venice, when is the application deadline?",
                "reasoning": "The user already named the intended scope.",
                "inferred_document_ids": ["venice"],
            }
        ),
        json.dumps(
            {
                "thinking": "Both documents are plausible, so I will inspect both.",
                "document_ids": ["venice", "piemonte"],
                "needs_clarification": False,
                "clarifying_question": None,
            }
        ),
        json.dumps({"thinking": "The deadline node is relevant.", "node_ids": ["0001"]}),
        json.dumps({"thinking": "The deadline node is relevant.", "node_ids": ["1001"]}),
        json.dumps(
            {
                "answer": "",
                "citations": [],
                "clarification_needed": True,
                "clarifying_question": "Please specify which university or region you want, because the retrieved deadlines come from different scholarship notices.",
            }
        ),
    ]

    result = answer_question("For Ca' Foscari University of Venice, when is the application deadline?", str(tmp_path), client)

    assert result.needs_clarification is True
    assert result.document_ids == ["venice", "piemonte"]
    assert "Please specify which university or region" in result.answer


def test_answer_question_uses_hype_rewrite_for_scope_shorthand(tmp_path):
    docs = [
        {
            "document_id": "piemonte_notice",
            "title": "Scholarship Notice",
            "source_path": "output/fixed/piemonte_notice.md",
            "summary": "Scholarship notice for students in Piedmont universities.",
            "metadata": {
                "title": "Scholarship Notice",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": None,
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Universities",
                    "node_id": "0001",
                    "line_num": 12,
                    "text": "Students enrolled at Piedmont universities, including the University of Turin, may apply.",
                    "nodes": [],
                },
                {
                    "title": "Deadlines",
                    "node_id": "0002",
                    "line_num": 24,
                    "text": "Applications close on September 9.",
                    "nodes": [],
                },
            ],
        },
        {
            "document_id": "liguria_notice",
            "title": "Competition Notice",
            "source_path": "output/fixed/liguria_notice.md",
            "summary": "Scholarship notice for the University of Genoa and Liguria AFAM institutions.",
            "metadata": {
                "title": "Competition Notice",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": None,
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Eligible students",
                    "node_id": "1001",
                    "line_num": 14,
                    "text": "Students enrolled at the University of Genoa and Liguria institutions may apply.",
                    "nodes": [],
                }
            ],
        },
    ]
    for payload in docs:
        path = tmp_path / f"{payload['document_id']}.pageindex.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            {
                "rewritten_question": "For the scholarship notice covering Piedmont universities and the University of Turin, what are the application deadlines?",
                "reasoning": "The shorthand 'Piemonte / Torino' most likely refers to the Piedmont/Turin scholarship notice.",
                "inferred_document_ids": ["piemonte_notice"],
            }
        ),
        json.dumps(
            {
                "thinking": "The Piedmont/Turin notice is the best scope match.",
                "document_ids": ["piemonte_notice"],
                "needs_clarification": False,
                "clarifying_question": None,
            }
        ),
        json.dumps({"thinking": "The deadlines node is directly relevant.", "node_ids": ["0002"]}),
        json.dumps(
            {
                "answer": "The application deadline is September 9.",
                "citations": [
                    {
                        "document_id": "piemonte_notice",
                        "document_title": "Scholarship Notice",
                        "node_id": "0002",
                        "node_title": "Deadlines",
                        "line_number": 24,
                    }
                ],
                "clarification_needed": False,
                "clarifying_question": None,
            }
        ),
    ]

    result = answer_question("What are the application deadlines in Piemonte / Torino?", str(tmp_path), client)

    assert result.answer == "The application deadline is September 9."
    assert result.document_ids == ["piemonte_notice"]
    assert "Rewrote question for retrieval" in (result.retrieval_notes or "")


def test_answer_question_searches_multiple_documents_for_comparison_intent(tmp_path):
    docs = [
        {
            "document_id": "venice",
            "title": "Scholarship Call",
            "source_path": "output/fixed/venice.md",
            "summary": "Contains application deadlines for Venice students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "Ca' Foscari University of Venice",
            },
            "scope_label": "Ca' Foscari University of Venice | Scholarship Call | 2025/26",
            "identity_terms": ["Ca' Foscari University of Venice", "Scholarship Call", "2025/26"],
            "search_profile": {
                "issuer": "Ca' Foscari University of Venice",
                "region": "Veneto",
                "covered_institutions": ["Ca' Foscari University of Venice"],
                "covered_cities": ["Venice"],
                "academic_year": "2025/26",
                "benefit_types": ["scholarship"],
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "0001",
                    "line_num": 18,
                    "text": "Applications close on October 31.",
                    "nodes": [],
                }
            ],
        },
        {
            "document_id": "piemonte",
            "title": "Scholarship Call",
            "source_path": "output/fixed/piemonte.md",
            "summary": "Contains application deadlines for Piedmont students.",
            "metadata": {
                "title": "Scholarship Call",
                "source": "explicit",
                "year": "2025/26",
                "document_type": "Notice",
                "organization": "EDISU Piemonte",
            },
            "scope_label": "EDISU Piemonte | Scholarship Call | 2025/26",
            "identity_terms": ["EDISU Piemonte", "Scholarship Call", "2025/26"],
            "search_profile": {
                "issuer": "EDISU Piemonte",
                "region": "Piedmont",
                "covered_institutions": ["University of Turin"],
                "covered_cities": ["Turin"],
                "academic_year": "2025/26",
                "benefit_types": ["scholarship"],
            },
            "doc_description": None,
            "structure": [
                {
                    "title": "Deadlines",
                    "node_id": "1001",
                    "line_num": 24,
                    "text": "Applications close on September 9.",
                    "nodes": [],
                }
            ],
        },
    ]
    for payload in docs:
        path = tmp_path / f"{payload['document_id']}.pageindex.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            {
                "rewritten_question": "Compare the application deadlines across all scholarship notices.",
                "reasoning": "The user explicitly asked for a cross-document comparison.",
                "inferred_document_ids": [],
            }
        ),
        json.dumps(
            {
                "thinking": "The user asked for a comparison, so both documents are relevant.",
                "document_ids": ["venice", "piemonte"],
                "needs_clarification": False,
                "clarifying_question": None,
            }
        ),
        json.dumps({"thinking": "The deadlines node is directly relevant.", "node_ids": ["0001"]}),
        json.dumps({"thinking": "The deadlines node is directly relevant.", "node_ids": ["1001"]}),
        json.dumps(
            {
                "answer": "Venice: October 31. Piemonte: September 9.",
                "citations": [],
                "clarification_needed": False,
                "clarifying_question": None,
            }
        ),
    ]

    result = answer_question("Compare the application deadlines across all scholarship notices.", str(tmp_path), client)

    assert result.needs_clarification is False
    assert result.document_ids == ["venice", "piemonte"]
    assert "Venice: October 31" in result.answer
