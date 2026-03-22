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
