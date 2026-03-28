"""Unit tests for each PageIndexSearchAgent stage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.domain.models.search import SearchCitation, SearchDocumentIndex, SearchSelectionDecision


def _make_mock_client(responses: list[str]) -> MagicMock:
    client = MagicMock()
    client.supports_structured_output = False
    client.create_message = MagicMock(side_effect=responses)
    return client


def _make_document(**overrides) -> SearchDocumentIndex:
    defaults = {
        "document_id": "doc1",
        "title": "Scholarship Notice",
        "source_path": "output/fixed/doc1.md",
        "summary": "Contains deadlines and eligibility.",
        "structure": [
            {
                "title": "Deadlines",
                "node_id": "0001",
                "line_num": 18,
                "text": "Applications close on April 1.",
                "nodes": [],
            }
        ],
    }
    defaults.update(overrides)
    return SearchDocumentIndex(**defaults)


class TestRewriteQuestion:
    def test_rewrite_returns_expanded_question(self):
        client = _make_mock_client([
            json.dumps({
                "rewritten_question": "What is the deadline for the EDISU scholarship?",
                "reasoning": "Added scope from catalog.",
                "inferred_document_ids": ["doc1"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        doc = _make_document()

        rewritten, reasoning, inferred_ids = agent.rewrite_question("What is the deadline?", [doc])

        assert rewritten == "What is the deadline for the EDISU scholarship?"
        assert reasoning == "Added scope from catalog."
        assert inferred_ids == ["doc1"]

    def test_rewrite_with_empty_documents(self):
        client = _make_mock_client([])
        agent = PageIndexSearchAgent(client)

        rewritten, reasoning, inferred_ids = agent.rewrite_question("What is the deadline?", [])

        assert rewritten == "What is the deadline?"
        assert reasoning is None
        assert inferred_ids == []

    def test_rewrite_filters_invalid_document_ids(self):
        client = _make_mock_client([
            json.dumps({
                "rewritten_question": "expanded question",
                "reasoning": "reason",
                "inferred_document_ids": ["doc1", "invalid_doc", "doc2"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        doc = _make_document(document_id="doc1")

        _, _, inferred_ids = agent.rewrite_question("question", [doc])

        assert inferred_ids == ["doc1"]

    def test_rewrite_limits_to_two_inferred_ids(self):
        client = _make_mock_client([
            json.dumps({
                "rewritten_question": "expanded",
                "reasoning": "r",
                "inferred_document_ids": ["doc1", "doc2", "doc3"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        docs = [
            _make_document(document_id="doc1"),
            _make_document(document_id="doc2"),
            _make_document(document_id="doc3"),
        ]

        _, _, inferred_ids = agent.rewrite_question("q", docs)

        assert len(inferred_ids) <= 2


class TestSelectDocuments:
    def test_single_document_returns_immediately(self):
        client = _make_mock_client([])
        agent = PageIndexSearchAgent(client)
        doc = _make_document()

        decision = agent.select_documents("What is the deadline?", [doc])

        assert decision.document_ids == ["doc1"]
        assert decision.needs_clarification is False
        # Should not have called the LLM
        assert client.create_message.call_count == 0

    def test_empty_documents(self):
        client = _make_mock_client([])
        agent = PageIndexSearchAgent(client)

        decision = agent.select_documents("question", [])

        assert decision.document_ids == []

    def test_multiple_documents_calls_llm(self):
        client = _make_mock_client([
            json.dumps({
                "thinking": "Doc1 is most relevant.",
                "document_ids": ["doc1"],
                "needs_clarification": False,
                "clarifying_question": None,
            })
        ])
        agent = PageIndexSearchAgent(client)
        docs = [_make_document(document_id="doc1"), _make_document(document_id="doc2")]

        decision = agent.select_documents("What is the deadline?", docs)

        assert decision.document_ids == ["doc1"]
        assert decision.needs_clarification is False

    def test_clarification_clears_document_ids(self):
        client = _make_mock_client([
            json.dumps({
                "thinking": "Ambiguous scope.",
                "document_ids": ["doc1"],
                "needs_clarification": True,
                "clarifying_question": "Which university?",
            })
        ])
        agent = PageIndexSearchAgent(client)
        docs = [_make_document(document_id="doc1"), _make_document(document_id="doc2")]

        decision = agent.select_documents("question", docs)

        assert decision.document_ids == []
        assert decision.needs_clarification is True
        assert decision.clarifying_question == "Which university?"

    def test_filters_invalid_ids(self):
        client = _make_mock_client([
            json.dumps({
                "thinking": "Selected.",
                "document_ids": ["doc1", "nonexistent"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        docs = [_make_document(document_id="doc1")]

        decision = agent.select_documents("q", docs)

        assert decision.document_ids == ["doc1"]


class TestSelectNodes:
    def test_returns_valid_node_ids(self):
        client = _make_mock_client([
            json.dumps({
                "thinking": "Deadlines section matches.",
                "node_ids": ["0001"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        doc = _make_document()

        node_ids, thinking = agent.select_nodes("What is the deadline?", doc)

        assert node_ids == ["0001"]
        assert thinking == "Deadlines section matches."

    def test_filters_invalid_node_ids(self):
        client = _make_mock_client([
            json.dumps({
                "thinking": "Selected.",
                "node_ids": ["0001", "9999"],
            })
        ])
        agent = PageIndexSearchAgent(client)
        doc = _make_document()

        node_ids, _ = agent.select_nodes("q", doc)

        assert node_ids == ["0001"]

    def test_limits_to_six_nodes(self):
        nodes = [
            {"title": f"Section {i}", "node_id": f"000{i}", "text": "text", "nodes": []}
            for i in range(10)
        ]
        client = _make_mock_client([
            json.dumps({
                "thinking": "All relevant.",
                "node_ids": [f"000{i}" for i in range(10)],
            })
        ])
        agent = PageIndexSearchAgent(client)
        doc = _make_document(structure=nodes)

        node_ids, _ = agent.select_nodes("q", doc)

        assert len(node_ids) <= 6


class TestAnswerFromContexts:
    def test_standard_answer(self):
        client = _make_mock_client([
            json.dumps({
                "answer": "The deadline is April 1.",
                "citations": [{
                    "document_id": "doc1",
                    "document_title": "Scholarship Notice",
                    "node_id": "0001",
                    "node_title": "Deadlines",
                    "line_number": 18,
                }],
                "clarification_needed": False,
            })
        ])
        agent = PageIndexSearchAgent(client)

        result = agent.answer_from_contexts(
            "When is the deadline?",
            [{"document_id": "doc1", "node_id": "0001", "text": "April 1."}],
            document_ids=["doc1"],
        )

        assert result.answer == "The deadline is April 1."
        assert len(result.citations) == 1
        assert result.needs_clarification is False

    def test_empty_answer_uses_fallback(self):
        client = _make_mock_client([
            json.dumps({
                "answer": "",
                "citations": [],
                "clarification_needed": True,
                "clarifying_question": "Which university?",
            })
        ])
        agent = PageIndexSearchAgent(client)

        result = agent.answer_from_contexts(
            "q", [{"text": "data"}], document_ids=["doc1"],
        )

        assert result.needs_clarification is True
        assert "Which university?" in result.answer

    def test_no_answer_at_all_uses_default(self):
        client = _make_mock_client([
            json.dumps({
                "answer": "",
                "citations": [],
            })
        ])
        agent = PageIndexSearchAgent(client)

        result = agent.answer_from_contexts(
            "q", [{"text": "data"}], document_ids=["doc1"],
        )

        assert "could not find" in result.answer.lower()


class TestParseCitations:
    def test_valid_citations_parsed(self):
        citations = PageIndexSearchAgent._parse_citations(
            [{"document_id": "d", "document_title": "T", "node_id": "n", "node_title": "N"}],
            [],
        )
        assert len(citations) == 1
        assert citations[0].document_id == "d"

    def test_invalid_citations_fall_back_to_contexts(self):
        citations = PageIndexSearchAgent._parse_citations(
            [{"bad_key": "x"}],  # Invalid
            [{"document_id": "d1", "node_id": "n1", "document_title": "T", "node_title": "N"}],
        )
        assert len(citations) == 1
        assert citations[0].document_id == "d1"

    def test_fallback_deduplicates(self):
        contexts = [
            {"document_id": "d1", "node_id": "n1", "document_title": "T", "node_title": "N"},
            {"document_id": "d1", "node_id": "n1", "document_title": "T", "node_title": "N"},
        ]
        citations = PageIndexSearchAgent._fallback_citations_from_contexts(contexts)
        assert len(citations) == 1

    def test_fallback_limits_to_four(self):
        contexts = [
            {"document_id": f"d{i}", "node_id": f"n{i}", "document_title": "T", "node_title": "N"}
            for i in range(10)
        ]
        citations = PageIndexSearchAgent._fallback_citations_from_contexts(contexts)
        assert len(citations) == 4
