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
    assert indexes[0].scope_label is None


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
    client.create_message.side_effect = [
        json.dumps(
            {
                "rewritten_question": "What are the application deadlines?",
                "reasoning": "The question is still ambiguous across documents.",
                "inferred_document_ids": [],
            }
        ),
        json.dumps(
            {
                "thinking": "The question is missing the university or region.",
                "document_ids": [],
                "needs_clarification": True,
                "clarifying_question": "Which scholarship notice do you mean: Ca' Foscari University of Venice or EDISU Piemonte?",
            }
        ),
    ]

    result = answer_question("What are the application deadlines?", str(tmp_path), client)

    assert result.needs_clarification is True
    assert result.document_ids == []
    assert "Which scholarship notice do you mean" in result.answer
    assert "EDISU Piemonte" in (result.clarifying_question or "")


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
