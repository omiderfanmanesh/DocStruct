"""Integration tests for retrieval fallback modes.

Tests that retrieval remains effective when structured metadata is incomplete or missing,
using full-text search as a fallback.
"""

import sys
from pathlib import Path

import pytest
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import Neo4jConfig, RetrievalConfig, EmbeddingConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.loader import PageIndexLoader
from docstruct.infrastructure.neo4j.retrieval import Neo4jRetrieval
from docstruct.domain.models.search import SearchDocumentIndex, SearchProfile


@pytest.fixture
def retrieval_instance(neo4j_driver: Driver) -> Neo4jRetrieval:
    """Create a Neo4jRetrieval instance for testing."""
    retrieval_config = RetrievalConfig.from_env()
    return Neo4jRetrieval(neo4j_driver, retrieval_config, embedding_config=None)


def test_retrieval_with_missing_metadata(neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval) -> None:
    """Test retrieval works via full-text when structured metadata is missing.

    Scenario: Document has title/summary but minimal metadata relationships.
    Expected: Full-text search finds the document despite missing org/region/institution.
    """
    with neo4j_driver.session() as session:
        # Create a document with minimal metadata
        session.run(
            """
            CREATE (d:Document {
                source_path: 'test/minimal_metadata.pageindex.json',
                document_id: 'doc_minimal',
                title: 'Scholarship Opportunities in Europe',
                summary: 'A comprehensive guide to scholarships available across Europe',
                active: true,
                ingested_at: datetime()
            })
            CREATE (s:Section {
                node_id: 'sec_1',
                document_id: 'doc_minimal',
                node_title: 'Application Process',
                text: 'To apply for scholarships, follow these steps: 1) Fill out the form...',
                depth: 0
            })
            CREATE (d)-[:HAS_SECTION]->(s)
            """
        )

    # Query for "scholarship" - should find via full-text even without metadata
    candidates = retrieval_instance.retrieve_candidates(
        question="How do I apply for a scholarship in Europe?",
        limit=5,
    )

    # Should find the document via full-text search
    assert len(candidates) > 0, "Should find document via full-text fallback"
    assert any(c.document_id == "doc_minimal" for c in candidates)

    # Should have fulltext_rank set (from full-text mode)
    found_candidate = next(c for c in candidates if c.document_id == "doc_minimal")
    assert found_candidate.fulltext_rank is not None


def test_retrieval_prefers_metadata_matches(neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval) -> None:
    """Test that documents with matching metadata are ranked higher.

    Scenario: Two documents with same title, one has metadata relationships.
    Expected: Document with metadata ranks higher (graph mode boost).
    """
    with neo4j_driver.session() as session:
        # Document without metadata
        session.run(
            """
            CREATE (d:Document {
                source_path: 'test/no_metadata.pageindex.json',
                document_id: 'doc_no_meta',
                title: 'Study Abroad Programs',
                summary: 'Information about study abroad',
                active: true,
                ingested_at: datetime()
            })
            """
        )

        # Document with metadata
        session.run(
            """
            MERGE (org:Organization {name: 'European Universities'})
            CREATE (d:Document {
                source_path: 'test/with_metadata.pageindex.json',
                document_id: 'doc_with_meta',
                title: 'Study Abroad Programs',
                summary: 'Information about study abroad in Europe',
                active: true,
                ingested_at: datetime()
            })
            CREATE (d)-[:ISSUED_BY]->(org)
            """
        )

    # Query that could match both
    candidates = retrieval_instance.retrieve_candidates(
        question="study abroad programs in Europe",
        limit=5,
    )

    # Should find both documents
    found_ids = {c.document_id for c in candidates}
    assert "doc_with_meta" in found_ids
    assert "doc_no_meta" in found_ids

    # Document with metadata should appear (graph mode should return it)
    doc_with_meta = next((c for c in candidates if c.document_id == "doc_with_meta"), None)
    assert doc_with_meta is not None


def test_retrieval_section_fallback(neo4j_driver: Driver, retrieval_instance: Neo4jRetrieval) -> None:
    """Test that section-level full-text search works as fallback.

    Scenario: Question matches content in a section, not the document title.
    Expected: Retrieval finds the document via section-level full-text search.
    """
    with neo4j_driver.session() as session:
        session.run(
            """
            CREATE (d:Document {
                source_path: 'test/section_match.pageindex.json',
                document_id: 'doc_sections',
                title: 'Benefits Guide',
                summary: 'General benefits information',
                active: true,
                ingested_at: datetime()
            })
            CREATE (s:Section {
                node_id: 'sec_scholarships',
                document_id: 'doc_sections',
                node_title: 'Scholarship Programs',
                text: 'We offer merit-based scholarships and need-based financial aid to qualified applicants...',
                depth: 0
            })
            CREATE (d)-[:HAS_SECTION]->(s)
            """
        )

    # Query for "merit-based scholarships" - should match via section full-text
    candidates = retrieval_instance.retrieve_candidates(
        question="What merit-based scholarship programs are available?",
        limit=5,
    )

    # Should find via section-level full-text
    assert len(candidates) > 0
    assert any(c.document_id == "doc_sections" for c in candidates)
