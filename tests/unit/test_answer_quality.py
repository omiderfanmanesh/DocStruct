"""Unit tests for answer quality safeguards."""

import pytest

from docstruct.domain.answer_quality import (
    AnswerQualityReport,
    assess_answer_quality,
    guard_empty_context,
)


class TestAssessAnswerQuality:
    def _make_context(self, **overrides) -> dict:
        defaults = {
            "document_id": "doc1",
            "document_title": "Test Document",
            "node_id": "node1",
            "node_title": "Section A",
            "text": "Applications close on April 1 for all students.",
        }
        defaults.update(overrides)
        return defaults

    def test_high_confidence_grounded_answer(self):
        contexts = [self._make_context()]
        citations = [{"document_id": "doc1", "node_id": "node1"}]
        report = assess_answer_quality(
            answer="The application deadline is April 1.",
            citations=citations,
            contexts=contexts,
            question="When is the deadline?",
        )
        assert report.confidence_label in ("high", "medium")
        assert report.has_grounded_citations is True
        assert report.empty_context is False

    def test_no_context_returns_insufficient(self):
        report = assess_answer_quality(
            answer="The deadline is April 1.",
            citations=[],
            contexts=[],
            question="When is the deadline?",
        )
        assert report.confidence_label == "insufficient"
        assert report.confidence_score == 0.0
        assert report.empty_context is True
        assert report.potential_hallucination is True

    def test_ungrounded_citations_flagged(self):
        contexts = [self._make_context(node_id="node1")]
        # Citation references a different node not in context
        citations = [{"document_id": "doc1", "node_id": "node_unknown"}]
        report = assess_answer_quality(
            answer="The deadline is April 1.",
            citations=citations,
            contexts=contexts,
        )
        assert report.citation_coverage == 0.0
        assert len(report.hallucination_indicators) > 0

    def test_fabricated_date_detected(self):
        contexts = [self._make_context(text="Applications close on April 1.")]
        report = assess_answer_quality(
            answer="The deadline is March 15.",  # Date not in context
            citations=[],
            contexts=contexts,
        )
        # Should detect the fabricated date
        assert report.potential_hallucination is True

    def test_fabricated_university_detected(self):
        contexts = [self._make_context(text="Students at University of Naples may apply.")]
        report = assess_answer_quality(
            answer="Students at University of Rome can apply.",
            citations=[],
            contexts=contexts,
        )
        assert report.potential_hallucination is True
        hallucination_text = " ".join(report.hallucination_indicators)
        assert "Rome" in hallucination_text or "not found" in hallucination_text

    def test_hedging_language_lowers_confidence(self):
        contexts = [self._make_context()]
        report = assess_answer_quality(
            answer="I'm not sure, but it seems the deadline might be April 1. Perhaps it could be later.",
            citations=[],
            contexts=contexts,
        )
        assert report.confidence_score < 0.6

    def test_limitation_acknowledgment_is_positive(self):
        contexts = [self._make_context(text="Short text.")]
        report = assess_answer_quality(
            answer="I could not find enough information. The context is insufficient to answer.",
            citations=[],
            contexts=contexts,
        )
        # Should not be flagged as hallucination since it acknowledges limitation
        assert report.confidence_label in ("low", "medium", "insufficient")

    def test_multiple_grounded_citations_boost_confidence(self):
        contexts = [
            self._make_context(node_id="node1"),
            self._make_context(node_id="node2"),
        ]
        citations = [
            {"document_id": "doc1", "node_id": "node1"},
            {"document_id": "doc1", "node_id": "node2"},
        ]
        report = assess_answer_quality(
            answer="The application deadline is April 1 as stated in Section A.",
            citations=citations,
            contexts=contexts,
        )
        assert report.citation_coverage == 1.0
        assert report.has_grounded_citations is True
        assert report.confidence_score >= 0.6


class TestGuardEmptyContext:
    def test_returns_message_for_empty_list(self):
        result = guard_empty_context([])
        assert result is not None
        assert "could not find" in result.lower()

    def test_returns_message_for_tiny_text(self):
        result = guard_empty_context([{"text": "ok"}])
        assert result is not None
        assert "too little" in result.lower()

    def test_returns_none_for_sufficient_context(self):
        result = guard_empty_context([{"text": "A" * 100}])
        assert result is None
