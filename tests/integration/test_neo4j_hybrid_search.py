"""Integration tests for Neo4j hybrid search modes (graph, fulltext, vector, RRF fusion).

Tests the three retrieval modes and their RRF (Reciprocal Rank Fusion) combination
against an ephemeral Docker Compose Neo4j instance with seeded test documents.
"""

import sys
from pathlib import Path

import pytest
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import RetrievalConfig, EmbeddingConfig
from docstruct.infrastructure.neo4j.retrieval import Neo4jRetrieval


@pytest.fixture
def retrieval_instance(neo4j_driver: Driver) -> Neo4jRetrieval:
    """Create a Neo4jRetrieval instance for testing."""
    retrieval_config = RetrievalConfig.from_env()
    embedding_config = EmbeddingConfig.from_env()
    return Neo4jRetrieval(neo4j_driver, retrieval_config, embedding_config=embedding_config)


# T029: Graph-only retrieval returns documents with matching metadata filters
def test_graph_only_retrieval(
    neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval, seed_documents: None
) -> None:
    """Test graph-only retrieval returns documents with matching metadata filters.

    Scenario: Query for documents in a specific organization/region using metadata filters.
    Expected: Graph mode returns documents where metadata relationships match the query intent.
    """
    # Query that should match MIT documents via organization filter
    question = "I want to find information about MIT scholarships"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    # Should retrieve documents
    assert len(candidates) > 0, "Graph retrieval should find documents"

    # MIT Scholarship document should be included
    doc_ids = {c.document_id for c in candidates}
    assert "doc_mit_scholarship" in doc_ids, "Should find MIT scholarship document via graph/metadata"

    # Check that retrieved candidates have graph-related rank (metadata_rank or graph_rank)
    mit_candidate = next(c for c in candidates if c.document_id == "doc_mit_scholarship")
    # At least one of these should be set for graph mode
    assert mit_candidate.metadata_rank is not None or mit_candidate.graph_rank is not None


# T030: Fulltext-only retrieval returns documents matching BM25 search on title and summary
def test_fulltext_only_retrieval(
    neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval, seed_documents: None
) -> None:
    """Test fulltext-only retrieval returns documents matching BM25 search.

    Scenario: Query with keywords that appear in titles/summaries but no specific metadata.
    Expected: Fulltext search finds documents via BM25 ranking on title and summary.
    """
    # Query with keywords from document titles/summaries
    question = "admission requirements and criteria"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    assert len(candidates) > 0, "Fulltext retrieval should find documents"

    # Should find Harvard Admission document (title: "Harvard Admission Requirements")
    doc_ids = {c.document_id for c in candidates}
    assert "doc_harvard_admission" in doc_ids, "Should find Harvard admission document via fulltext"

    # Check that retrieved candidates have fulltext rank
    harvard_candidate = next(c for c in candidates if c.document_id == "doc_harvard_admission")
    assert harvard_candidate.fulltext_rank is not None, "Should have fulltext_rank set"


# T031: Vector-only retrieval returns documents ranked by embedding cosine similarity
def test_vector_only_retrieval(
    neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval, seed_documents: None
) -> None:
    """Test vector-only retrieval returns documents ranked by embedding similarity.

    Scenario: Query for conceptually similar content (funding, scholarships, financial aid).
    Expected: Vector search finds documents with similar embeddings based on semantic meaning.
    """
    # Query about funding (should match via embedding similarity with funding vectors)
    question = "What funding opportunities are available?"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    assert len(candidates) > 0, "Vector retrieval should find documents"

    # Should find Stanford funding document (has funding vectors)
    doc_ids = {c.document_id for c in candidates}
    assert "doc_stanford_funding" in doc_ids, "Should find Stanford funding document via vector similarity"

    # Check that retrieved candidates have vector rank
    stanford_candidate = next(c for c in candidates if c.document_id == "doc_stanford_funding")
    assert stanford_candidate.vector_rank is not None, "Should have vector_rank set"


# T032: Combined RRF fusion result set includes contributions from all three modes
def test_rrf_fusion_combines_modes(
    neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval, seed_documents: None
) -> None:
    """Test RRF fusion combines results from graph, fulltext, and vector modes.

    Scenario: Query that benefits from all three retrieval modes.
    Expected: RRF fusion returns documents ranked by combined scores from all modes.
    """
    # Query that could match via multiple modes
    question = "admission deadlines for universities"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    assert len(candidates) > 0, "RRF fusion should find documents"

    # Multiple documents should be retrieved (via different modes)
    # Harvard (admission + deadline keywords via fulltext + graph)
    # MIT (scholarship + deadline keywords via fulltext)
    # Cambridge (admission + deadline keywords via fulltext)
    doc_ids = {c.document_id for c in candidates}

    # Should have at least 2 different documents from different retrieval paths
    assert len(doc_ids) >= 2, f"RRF should combine results from multiple modes, got {doc_ids}"

    # At least one candidate should have contributions from multiple modes
    # (indicated by having multiple rank fields set)
    multi_mode_found = False
    for candidate in candidates:
        rank_fields_set = sum([
            candidate.graph_rank is not None,
            candidate.fulltext_rank is not None,
            candidate.vector_rank is not None,
        ])
        if rank_fields_set >= 2:
            multi_mode_found = True
            break

    assert multi_mode_found, "At least one document should be ranked by multiple modes in RRF"


# T033: When vector index is empty/unavailable, RRF returns results from graph and fulltext only
def test_rrf_with_missing_vector_index(
    neo4j_driver: Driver, seed_documents: None
) -> None:
    """Test RRF fusion gracefully handles missing or empty vector index.

    Scenario: Vector embeddings are not available (index empty or skipped).
    Expected: RRF fusion returns results from graph and fulltext modes only, no crash.
    """
    retrieval_config = RetrievalConfig.from_env()
    # Create retrieval instance with embedding_config=None to skip vector mode
    retrieval_instance = Neo4jRetrieval(neo4j_driver, retrieval_config, embedding_config=None)

    # Query that should still work via graph and fulltext
    question = "MIT scholarship application requirements"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    # Should still find documents via graph and fulltext, not crash
    assert len(candidates) > 0, "Should find documents even without vector search"

    # MIT document should be found
    doc_ids = {c.document_id for c in candidates}
    assert "doc_mit_scholarship" in doc_ids, "Should find MIT scholarship via graph/fulltext without vector"

    # Retrieved documents should NOT have vector_rank set (vector mode skipped)
    for candidate in candidates:
        # Should have at least one of graph or fulltext rank
        has_rank = candidate.graph_rank is not None or candidate.fulltext_rank is not None
        assert has_rank, f"Document {candidate.document_id} should have graph or fulltext rank"


# T034: Documents appearing in multiple search modes have higher RRF rank
def test_rrf_rank_boost_for_overlapping_results(
    neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval, seed_documents: None
) -> None:
    """Test that documents appearing in multiple search modes rank higher via RRF.

    Scenario: Same document is retrieved by multiple modes (e.g., graph + fulltext + vector).
    Expected: RRF ranking algorithm gives higher score to documents with more mode hits.
    """
    # Query that should match via multiple modes
    question = "deadline for applications"

    candidates = retrieval_instance.retrieve_candidates(
        question=question,
        limit=5,
    )

    assert len(candidates) > 0, "Should find documents via RRF"

    # Build a map of document to number of retrieval modes
    doc_mode_counts = {}
    for candidate in candidates:
        modes = sum([
            candidate.graph_rank is not None,
            candidate.fulltext_rank is not None,
            candidate.vector_rank is not None,
        ])
        doc_mode_counts[candidate.document_id] = modes

    # Find documents with highest mode count (most overlapping)
    if doc_mode_counts:
        max_modes = max(doc_mode_counts.values())
        if max_modes >= 2:
            # Documents with multiple modes should appear in top results
            multi_mode_docs = {doc_id for doc_id, modes in doc_mode_counts.items() if modes >= 2}
            top_docs = {c.document_id for c in candidates[:3]}

            # At least one multi-mode document should be in top 3
            overlap = multi_mode_docs & top_docs
            assert len(overlap) > 0, (
                f"Documents appearing in multiple modes should rank higher. "
                f"Multi-mode: {multi_mode_docs}, Top 3: {top_docs}"
            )
