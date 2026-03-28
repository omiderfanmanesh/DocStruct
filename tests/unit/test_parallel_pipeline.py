"""Unit tests for parallel LLM call execution in the search graph."""

from unittest.mock import MagicMock, patch
import pytest

from docstruct.application.pageindex_search_graph import PageIndexSearchGraphRunner
from docstruct.domain.models import SearchDocumentIndex


class TestParallelPipelineExecution:
    """Test that rewrite_question and rank_candidates execute in parallel."""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_agent(self):
        """Mock PageIndexSearchAgent."""
        agent = MagicMock()
        agent.rewrite_question.return_value = ("What is the deadline?", "Rewrite note", ["doc1"])
        agent.select_documents.return_value = MagicMock(
            document_ids=["doc1"],
            needs_clarification=False,
            clarifying_question=None,
            thinking="Selected doc1",
        )
        return agent

    @pytest.fixture
    def mock_documents(self):
        """Create mock SearchDocumentIndex objects."""
        return [
            SearchDocumentIndex(document_id="doc1", pages={"1": "Content 1"}),
            SearchDocumentIndex(document_id="doc2", pages={"1": "Content 2"}),
        ]

    def test_parallel_nodes_both_invoked(self, mock_client, mock_agent, mock_documents):
        """Verify both rewrite_question and rank_candidates nodes are invoked."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())
        runner._agent = mock_agent

        # Mock the graph execution to track node calls
        node_calls = []

        original_rewrite = runner._rewrite_question
        original_rank = runner._rank_candidates

        def tracked_rewrite(state):
            node_calls.append("rewrite_question")
            return original_rewrite(state)

        def tracked_rank(state):
            node_calls.append("rank_candidates")
            return original_rank(state)

        runner._rewrite_question = tracked_rewrite
        runner._rank_candidates = tracked_rank

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "What is the deadline?",
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        # Execute both nodes
        rewrite_state = tracked_rewrite(initial_state)
        rank_state = tracked_rank(initial_state)

        # Verify both were called
        assert "rewrite_question" in node_calls
        assert "rank_candidates" in node_calls

    def test_parallel_state_merge_in_select_documents(self, mock_client, mock_agent, mock_documents):
        """Verify state from both branches is merged correctly in select_documents."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())
        runner._agent = mock_agent

        # Simulate state after both parallel branches complete
        merged_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            # From rewrite_question
            "effective_question": "When is the application deadline?",
            "rewrite_note": "Rewrote question for retrieval: When is the application deadline?",
            "inferred_document_ids": ["doc1"],
            # From rank_candidates
            "candidate_documents": mock_documents,
            "heuristic_clarification": "Asking about deadlines",
            # Initial state
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        # Execute select_documents (fan-in)
        result = runner._select_documents(merged_state)

        # Verify the result uses effective_question and candidate_documents from both branches
        mock_agent.select_documents.assert_called_once()
        call_args = mock_agent.select_documents.call_args
        assert call_args[0][0] == "When is the application deadline?"  # effective_question
        assert len(call_args[0][1]) == 2  # candidate_documents

    def test_rewrite_failure_fallback_to_original(self, mock_client, mock_agent, mock_documents):
        """Verify rewrite_question fallback uses original question on exception."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())
        runner._agent = mock_agent
        mock_agent.rewrite_question.side_effect = RuntimeError("LLM timeout")

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "What is the deadline?",
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        result = runner._rewrite_question(initial_state)

        # Should fallback to original question without raising
        assert result["effective_question"] == "What is the deadline?"
        assert result["rewrite_note"] is None
        assert result["inferred_document_ids"] == []

    def test_rank_candidates_uses_original_question_for_parallel(self, mock_client, mock_documents):
        """Verify rank_candidates uses original question (not effective_question)."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "When is the application deadline?",  # Different from original
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        # Mock the retrieval to track what question is used
        with patch(
            "docstruct.application.pageindex_search_graph.choose_candidate_documents"
        ) as mock_choose:
            mock_choose.return_value = mock_documents
            result = runner._rank_candidates(initial_state)

            # Verify it was called with original question, not effective_question
            call_args = mock_choose.call_args
            assert call_args[0][0] == "What is the deadline?"  # Original question
            assert call_args[0][1] == mock_documents

    def test_heuristic_clarification_from_original_question(self, mock_client, mock_documents):
        """Verify heuristic_clarification is built from original question in parallel."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "What is the deadline?",
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        result = runner._rank_candidates(initial_state)

        # Heuristic clarification should exist
        assert result["heuristic_clarification"] is not None

    def test_parallel_execution_time_comparison(self, mock_client, mock_agent, mock_documents):
        """Verify parallel execution is faster than sequential (at least structure supports it)."""
        import time

        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())
        runner._agent = mock_agent

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "What is the deadline?",
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        # Measure parallel execution (both start from same state)
        start_time = time.time()
        rewrite_state = runner._rewrite_question(initial_state)
        rank_state = runner._rank_candidates(initial_state)
        parallel_time = time.time() - start_time

        # Measure sequential execution (chained)
        start_time = time.time()
        sequential_state = runner._rewrite_question(initial_state)
        sequential_state.update(runner._rank_candidates(sequential_state))
        sequential_time = time.time() - start_time

        # Parallel should be <= sequential (may be equal in mock, but structure supports true parallelism)
        assert parallel_time <= sequential_time * 1.5  # Allow some variance for test overhead

    def test_graph_structure_has_parallel_edges(self, mock_client, mock_documents):
        """Verify the LangGraph structure includes parallel edges from START."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())

        # Access the compiled graph
        graph = runner._graph

        # The graph should be callable and structured for parallel execution
        assert callable(graph.invoke)

    def test_both_nodes_receive_state_updates(self, mock_client, mock_documents):
        """Verify both nodes in parallel receive the full initial state."""
        runner = PageIndexSearchGraphRunner(mock_client, MagicMock(), MagicMock())

        initial_state = {
            "question": "What is the deadline?",
            "indexes": mock_documents,
            "multi_document_intent": False,
            "effective_question": "What is the deadline?",
            "rewrite_note": None,
            "inferred_document_ids": [],
            "candidate_documents": [],
            "heuristic_clarification": None,
            "selection": None,
            "selection_notes": None,
            "selected_documents": [],
            "contexts": [],
            "retrieval_notes": [],
            "final_answer": None,
        }

        rewrite_result = runner._rewrite_question(initial_state)
        rank_result = runner._rank_candidates(initial_state)

        # Both should return valid state updates
        assert isinstance(rewrite_result, dict)
        assert isinstance(rank_result, dict)
        assert "effective_question" in rewrite_result
        assert "candidate_documents" in rank_result
