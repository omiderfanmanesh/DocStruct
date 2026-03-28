"""Unit tests for pageindex_search helper functions."""

import pytest

from docstruct.domain.models.search import SearchDocumentIndex, SearchProfile
from docstruct.domain.pageindex_search import (
    build_context_blocks,
    build_scope_clarification,
    build_tree_outline,
    choose_candidate_documents,
    fallback_node_matches,
    find_ambiguous_candidate_documents,
    question_has_scope_or_detail_hint,
    question_mentions_document_scope,
    question_requests_multi_document_answer,
    question_targets_deadlines,
    question_targets_documentation,
    score_document_match,
    tokenize,
)


def _make_doc(**overrides) -> SearchDocumentIndex:
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


class TestTokenize:
    def test_basic(self):
        tokens = tokenize("What is the application deadline?")
        assert "what" in tokens
        assert "application" in tokens
        assert "deadline" in tokens
        # Short words are excluded
        assert "is" not in tokens
        assert "the" not in tokens

    def test_none_input(self):
        assert tokenize(None) == set()

    def test_empty(self):
        assert tokenize("") == set()


class TestQuestionClassifiers:
    def test_targets_documentation(self):
        assert question_targets_documentation("What documents are needed?") is True
        assert question_targets_documentation("What is the deadline?") is False
        assert question_targets_documentation("Do I need a certificate?") is True

    def test_targets_deadlines(self):
        assert question_targets_deadlines("When is the deadline?") is True
        assert question_targets_deadlines("What documents are needed?") is False

    def test_multi_document_intent(self):
        assert question_requests_multi_document_answer("Compare the deadlines") is True
        assert question_requests_multi_document_answer("What is the deadline?") is False
        assert question_requests_multi_document_answer("Show all documents") is True

    def test_scope_or_detail_hint(self):
        assert question_has_scope_or_detail_hint("What is the deadline for EDISU Piemonte?") is True
        # Very generic question with only common words
        assert question_has_scope_or_detail_hint("What are the deadlines?") is False


class TestScoreDocumentMatch:
    def test_basic_scoring(self):
        doc = _make_doc(title="Scholarship Notice")
        score = score_document_match("When is the scholarship deadline?", doc)
        assert score > 0

    def test_scope_mention_bonus(self):
        doc = _make_doc(
            title="EDISU Piemonte Notice",
            search_profile=SearchProfile(
                issuer="EDISU Piemonte",
                region="Piedmont",
                covered_institutions=["University of Turin"],
            ),
        )
        score_with_scope = score_document_match("EDISU Piemonte deadline", doc)
        score_without = score_document_match("What is the deadline?", doc)
        assert score_with_scope > score_without


class TestChooseCandidateDocuments:
    def test_returns_top_candidates(self):
        docs = [
            _make_doc(document_id="d1", title="Scholarship Notice"),
            _make_doc(document_id="d2", title="Housing Rules"),
        ]
        result = choose_candidate_documents("scholarship deadline", docs, limit=2)
        assert len(result) >= 1
        # Scholarship doc should be ranked higher
        assert result[0].document_id == "d1"

    def test_empty_question_returns_first_n(self):
        docs = [_make_doc(document_id=f"d{i}") for i in range(5)]
        result = choose_candidate_documents("", docs, limit=3)
        assert len(result) == 3


class TestFindAmbiguousCandidates:
    def test_no_ambiguity_with_single_doc(self):
        assert find_ambiguous_candidate_documents("q", [_make_doc()]) == []

    def test_no_ambiguity_with_multi_doc_intent(self):
        docs = [_make_doc(document_id="d1"), _make_doc(document_id="d2")]
        assert find_ambiguous_candidate_documents("Compare all documents", docs) == []


class TestFallbackNodeMatches:
    def test_returns_matching_nodes(self):
        doc = _make_doc(structure=[
            {"title": "Deadlines", "node_id": "0001", "text": "Applications close on April 1.", "nodes": []},
            {"title": "Ranking", "node_id": "0002", "text": "Final ranking list.", "nodes": []},
        ])
        node_ids = fallback_node_matches("When is the application deadline?", doc, limit=2)
        assert "0001" in node_ids

    def test_ranking_penalty(self):
        doc = _make_doc(structure=[
            {"title": "Deadlines", "node_id": "0001", "text": "Applications close on April 1.", "nodes": []},
            {"title": "Ranking", "node_id": "0002", "text": "Ranking list published.", "nodes": []},
        ])
        node_ids = fallback_node_matches("When is the application deadline?", doc, limit=1)
        assert node_ids[0] == "0001"


class TestBuildTreeOutline:
    def test_basic_outline(self):
        structure = [
            {"title": "A", "node_id": "1", "summary": "Section A summary", "nodes": [
                {"title": "A.1", "node_id": "1.1", "text": "Subsection text", "nodes": []},
            ]},
        ]
        outline = build_tree_outline(structure, max_nodes=10)
        assert len(outline) == 1
        assert outline[0]["title"] == "A"
        assert len(outline[0]["nodes"]) == 1

    def test_max_nodes_limit(self):
        structure = [
            {"title": f"Section {i}", "node_id": str(i), "text": "text", "nodes": []}
            for i in range(100)
        ]
        outline = build_tree_outline(structure, max_nodes=5)
        assert len(outline) == 5


class TestBuildContextBlocks:
    def test_basic_context(self):
        doc = _make_doc()
        contexts = build_context_blocks(doc, ["0001"], question="When is the deadline?")
        assert len(contexts) >= 1
        assert contexts[0]["document_id"] == "doc1"
        assert contexts[0]["node_id"] == "0001"
        assert "April 1" in contexts[0]["text"]

    def test_missing_node_ids_skipped(self):
        doc = _make_doc()
        contexts = build_context_blocks(doc, ["nonexistent"], question="q")
        assert len(contexts) == 0

    def test_max_chars_respected(self):
        long_text = "A" * 5000
        doc = _make_doc(structure=[
            {"title": "Long", "node_id": "0001", "text": long_text, "nodes": []},
        ])
        contexts = build_context_blocks(doc, ["0001"], question="q", max_chars=100)
        for ctx in contexts:
            assert len(ctx["text"]) <= 103  # 100 + "..."


class TestBuildScopeClarification:
    def test_no_clarification_with_single_doc(self):
        assert build_scope_clarification("q", [_make_doc()]) is None

    def test_no_clarification_with_multi_doc_intent(self):
        docs = [
            _make_doc(document_id="d1", search_profile=SearchProfile(issuer="A")),
            _make_doc(document_id="d2", search_profile=SearchProfile(issuer="B")),
        ]
        assert build_scope_clarification("Compare all scholarships", docs) is None

    def test_clarification_for_ambiguous_multi_scope(self):
        docs = [
            _make_doc(
                document_id="d1",
                search_profile=SearchProfile(
                    issuer="EDISU Piemonte",
                    region="Piedmont",
                    covered_institutions=["University of Turin"],
                    covered_cities=["Turin"],
                ),
            ),
            _make_doc(
                document_id="d2",
                search_profile=SearchProfile(
                    issuer="Ca' Foscari",
                    region="Veneto",
                    covered_institutions=["Ca' Foscari University of Venice"],
                    covered_cities=["Venice"],
                ),
            ),
        ]
        result = build_scope_clarification("What are the deadlines?", docs)
        assert result is not None
        assert "specify" in result.lower()
