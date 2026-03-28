"""Unit tests for Reciprocal Rank Fusion."""

import pytest

from docstruct.domain.rrf import reciprocal_rank_fusion


class TestReciprocalRankFusion:
    def test_single_list(self):
        result = reciprocal_rank_fusion([["doc1", "doc2", "doc3"]])
        assert len(result) == 3
        ids = [item[0] for item in result]
        assert ids == ["doc1", "doc2", "doc3"]
        # Scores should be decreasing
        scores = [item[1] for item in result]
        assert scores[0] > scores[1] > scores[2]

    def test_two_lists_fusion(self):
        list1 = ["doc1", "doc2", "doc3"]
        list2 = ["doc2", "doc1", "doc4"]
        result = reciprocal_rank_fusion([list1, list2])
        ids = [item[0] for item in result]
        # doc1 and doc2 should be tied or close (appear in both)
        assert "doc1" in ids[:2]
        assert "doc2" in ids[:2]
        # doc3 and doc4 should be lower
        assert len(result) == 4

    def test_empty_lists_ignored(self):
        result = reciprocal_rank_fusion([[], ["doc1", "doc2"], []])
        assert len(result) == 2

    def test_all_empty_returns_empty(self):
        result = reciprocal_rank_fusion([[], []])
        assert result == []

    def test_no_lists_returns_empty(self):
        result = reciprocal_rank_fusion([])
        assert result == []

    def test_limit(self):
        result = reciprocal_rank_fusion(
            [["a", "b", "c", "d", "e"]], limit=3
        )
        assert len(result) == 3

    def test_custom_k(self):
        result_k10 = reciprocal_rank_fusion([["a", "b"]], k=10)
        result_k60 = reciprocal_rank_fusion([["a", "b"]], k=60)
        # With lower k, the score difference between ranks is larger
        diff_k10 = result_k10[0][1] - result_k10[1][1]
        diff_k60 = result_k60[0][1] - result_k60[1][1]
        assert diff_k10 > diff_k60

    def test_score_formula_correctness(self):
        result = reciprocal_rank_fusion([["doc1", "doc2"]], k=60)
        # doc1 at rank 1: 1/(60+1)
        # doc2 at rank 2: 1/(60+2)
        expected_doc1 = 1.0 / 61
        expected_doc2 = 1.0 / 62
        assert abs(result[0][1] - expected_doc1) < 1e-10
        assert abs(result[1][1] - expected_doc2) < 1e-10

    def test_three_list_fusion(self):
        list1 = ["a", "b", "c"]
        list2 = ["b", "c", "a"]
        list3 = ["c", "a", "b"]
        result = reciprocal_rank_fusion([list1, list2, list3])
        # All three appear in all lists at different ranks
        # Due to symmetry, scores should be very close
        scores = {item[0]: item[1] for item in result}
        assert abs(scores["a"] - scores["b"]) < 0.001
        assert abs(scores["b"] - scores["c"]) < 0.001
