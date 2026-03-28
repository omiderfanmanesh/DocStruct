"""Integration tests for retrieval with vector mode disabled."""

import sys
import os
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import Neo4jConfig, RetrievalConfig, EmbeddingConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.loader import PageIndexLoader
from docstruct.infrastructure.neo4j.retrieval import Neo4jRetrieval


@pytest.fixture
def retrieval_instance_no_vector(neo4j_driver: Driver) -> Neo4jRetrieval:
    """Create a Neo4jRetrieval instance with vector mode disabled."""
    retrieval_config = RetrievalConfig.from_env()
    # Override to disable vector mode
    retrieval_config.enable_vector = False
    return Neo4jRetrieval(neo4j_driver, retrieval_config, embedding_config=None)


def test_retrieval_returns_candidates_without_vector(neo4j_driver: Driver, retrieval_instance_no_vector: Neo4jRetrieval) -> None:
    """Test retrieval returns candidates via graph + full-text even when vector mode is disabled."""
    with neo4j_driver.session() as session:
        # Create test documents with metadata relationships
        session.run(
            """
            MERGE (org:Organization {name: 'Test University'})
            CREATE (d:Document {
                source_path: 'test/no_vector.pageindex.json',
                document_id: 'doc_no_vector',
                title: 'Scholarship Information',
                summary: 'Information about scholarships and financial aid',
                active: true,
                ingested_at: datetime()
            })
            CREATE (d)-[:ISSUED_BY]->(org)
            """
        )

    # Query for documents
    candidates = retrieval_instance_no_vector.retrieve_candidates(
        question="What scholarships are available?",
        query_embedding=None,  # No vector embedding
        limit=5,
    )

    # Should find document via graph + full-text (no vector needed)
    assert len(candidates) > 0, "Should find candidates without vector mode"
    assert any(c.document_id == "doc_no_vector" for c in candidates)

    # Verify no vector_rank is set (vector mode disabled)
    found = next(c for c in candidates if c.document_id == "doc_no_vector")
    assert found.vector_rank is None, "Vector rank should be None when vector mode disabled"


def test_retrieval_no_vector_mode_no_api_calls(neo4j_driver: Driver, retrieval_instance_no_vector: Neo4jRetrieval) -> None:
    """Test that with vector mode disabled, no embedding API calls are made."""
    with neo4j_driver.session() as session:
        # Create test data
        session.run(
            """
            CREATE (d:Document {
                source_path: 'test/api_call_test.pageindex.json',
                document_id: 'doc_api_test',
                title: 'Test Document',
                summary: 'This is a test',
                active: true,
                ingested_at: datetime()
            })
            """
        )

    # Mock embedding calls to verify they are not made
    with patch("docstruct.infrastructure.embeddings.openai_embedder.OpenAI") as mock_openai:
        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2") as mock_cohere:
            # Run retrieval
            candidates = retrieval_instance_no_vector.retrieve_candidates(
                question="test query",
                query_embedding=None,
                limit=5,
            )

            # Verify no embedding API calls were made
            mock_openai.assert_not_called()
            mock_cohere.assert_not_called()
            assert len(candidates) > 0


def test_retrieval_respects_enable_vector_flag(neo4j_driver: Driver) -> None:
    """Test that RETRIEVAL_ENABLE_VECTOR env var is respected."""
    # Disable vector mode explicitly
    with patch.dict(os.environ, {"RETRIEVAL_ENABLE_VECTOR": "false"}):
        retrieval_config = RetrievalConfig.from_env()
        assert retrieval_config.enable_vector is False

    # Enable vector mode explicitly
    with patch.dict(os.environ, {"RETRIEVAL_ENABLE_VECTOR": "true"}):
        retrieval_config = RetrievalConfig.from_env()
        assert retrieval_config.enable_vector is True


def test_retrieval_graph_and_fulltext_only(neo4j_driver: Driver, retrieval_instance_no_vector: Neo4jRetrieval) -> None:
    """Test that graph and full-text modes work independently without vector mode."""
    with neo4j_driver.session() as session:
        # Create document with metadata (for graph mode)
        session.run(
            """
            MERGE (org:Organization {name: 'Graph Test Org'})
            CREATE (d:Document {
                source_path: 'test/graph_only.pageindex.json',
                document_id: 'doc_graph_only',
                title: 'Graph Test Document',
                summary: 'Document with metadata relationships',
                active: true,
                ingested_at: datetime()
            })
            CREATE (d)-[:ISSUED_BY]->(org)
            """
        )

        # Create document without metadata (for full-text only)
        session.run(
            """
            CREATE (d:Document {
                source_path: 'test/fulltext_only.pageindex.json',
                document_id: 'doc_fulltext_only',
                title: 'Full-Text Only Document',
                summary: 'Document with excellent full-text search keywords',
                active: true,
                ingested_at: datetime()
            })
            """
        )

    # Query that matches both documents via different modes
    candidates = retrieval_instance_no_vector.retrieve_candidates(
        question="test document",
        query_embedding=None,
        limit=10,
    )

    found_ids = {c.document_id for c in candidates}
    assert "doc_graph_only" in found_ids, "Graph mode should find document with metadata"
    assert "doc_fulltext_only" in found_ids, "Full-text mode should find document by keyword"
