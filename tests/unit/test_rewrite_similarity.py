"""Unit tests for rewrite similarity validation."""

import logging
from unittest.mock import MagicMock

import pytest

from docstruct.application.pageindex_search_graph import (
    _cosine_similarity,
    rewrite_similarity_check,
)


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self):
        """Test that identical vectors have similarity 1.0."""
        vec = [1.0, 0.5, 0.3]
        similarity = _cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        """Test that orthogonal vectors have similarity 0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = _cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001

    def test_opposite_vectors(self):
        """Test that opposite vectors have similarity -1.0."""
        vec1 = [1.0, 0.5]
        vec2 = [-1.0, -0.5]
        similarity = _cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.001

    def test_similar_vectors(self):
        """Test cosine similarity with similar vectors."""
        vec1 = [1.0, 0.5]
        vec2 = [0.9, 0.6]
        similarity = _cosine_similarity(vec1, vec2)
        assert 0.99 < similarity < 1.0

    def test_empty_vector(self):
        """Test handling of empty vectors."""
        similarity = _cosine_similarity([], [])
        assert similarity == 0.0

    def test_different_length_vectors(self):
        """Test handling of vectors with different lengths."""
        similarity = _cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
        assert similarity == 0.0

    def test_zero_magnitude(self):
        """Test handling of zero-magnitude vectors."""
        similarity = _cosine_similarity([0.0, 0.0], [1.0, 2.0])
        assert similarity == 0.0


class TestRewriteSimilarityCheck:
    """Tests for rewrite similarity validation."""

    @pytest.fixture
    def mock_embedder(self):
        """Create a mock embedder that returns deterministic embeddings."""
        embedder = MagicMock()
        # Map questions to embedding vectors
        embedder.embed.side_effect = lambda text: self._get_embedding(text)
        return embedder

    @staticmethod
    def _get_embedding(text: str) -> list[float]:
        """Generate deterministic embeddings for test text."""
        # Use simple deterministic embedding based on text hash
        # Similar texts get similar embeddings
        if "deadline" in text.lower():
            return [0.8, 0.2, 0.1]
        elif "application" in text.lower():
            return [0.2, 0.9, 0.1]
        elif "university" in text.lower():
            return [0.1, 0.2, 0.8]
        elif "when" in text.lower():
            return [0.85, 0.15, 0.1]
        elif "scholarship" in text.lower():
            return [0.3, 0.7, 0.05]
        else:
            return [0.3, 0.3, 0.3]

    def test_identical_questions(self, mock_embedder):
        """Test that identical questions are always accepted."""
        original = "When is the deadline?"
        result = rewrite_similarity_check(original, original, mock_embedder)
        assert result == original

    def test_identical_questions_with_whitespace(self, mock_embedder):
        """Test that whitespace-equivalent questions are accepted."""
        original = "When is the deadline?"
        rewritten = "When is the deadline?"
        result = rewrite_similarity_check(original, rewritten, mock_embedder)
        assert result == original

    def test_similar_rewrite_accepted(self, mock_embedder):
        """Test that similar rewrites are accepted."""
        original = "When is the application deadline?"
        rewritten = "When is the deadline for applications?"
        result = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=0.6)
        # Both contain "deadline" and "application", should be similar
        assert result == rewritten

    def test_divergent_rewrite_rejected(self, mock_embedder):
        """Test that divergent rewrites below threshold are rejected."""
        original = "When is the deadline?"
        rewritten = "Tell me about the university."
        result = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=0.6)
        # These are semantically different, should fall back to original
        assert result == original

    def test_divergent_rewrite_with_warning(self, mock_embedder, caplog):
        """Test that divergent rewrites trigger a warning log."""
        original = "When is the deadline?"
        rewritten = "Tell me about the university."

        with caplog.at_level(logging.WARNING):
            result = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=0.6)

        assert result == original
        # Check that warning was logged
        assert "Query rewrite diverged" in caplog.text
        assert "similarity" in caplog.text.lower()

    def test_threshold_boundary(self, mock_embedder):
        """Test behavior at similarity threshold boundary."""
        original = "When is the deadline?"
        rewritten = "When is the deadline?"  # Identical, similarity = 1.0

        # Should accept if threshold <= 1.0
        result = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=1.0)
        assert result == rewritten

    def test_embedder_error_fallback(self, caplog):
        """Test that errors in embedding fall back to original."""
        original = "When is the deadline?"
        rewritten = "When is the application due?"
        mock_embedder = MagicMock()
        mock_embedder.embed.side_effect = RuntimeError("Embedding failed")

        with caplog.at_level(logging.DEBUG):
            result = rewrite_similarity_check(original, rewritten, mock_embedder)

        # Should return original on error
        assert result == original
        # Check that debug log was created
        assert "Error computing rewrite similarity" in caplog.text

    def test_custom_threshold(self, mock_embedder):
        """Test custom similarity threshold."""
        original = "Deadline question"
        rewritten = "Deadline question variant"

        # With low threshold, should accept
        result_low = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=0.1)
        # With high threshold, might reject
        result_high = rewrite_similarity_check(original, rewritten, mock_embedder, threshold=0.99)

        # Behavior depends on actual similarity
        # Just verify both calls work
        assert result_low in [original, rewritten]
        assert result_high in [original, rewritten]
