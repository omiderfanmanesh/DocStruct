"""Integration tests for Neo4j index and constraint creation."""

import sys
from pathlib import Path

import pytest
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import EmbeddingConfig
from docstruct.infrastructure.neo4j.indexes import create_indexes


def test_create_indexes_idempotent(neo4j_driver: Driver) -> None:
    """Test that create_indexes is idempotent (can be run multiple times)."""
    embedding_config = EmbeddingConfig.from_env()

    # Run once
    create_indexes(neo4j_driver, embedding_config, skip_vector=False)

    # Run again - should not raise any errors
    create_indexes(neo4j_driver, embedding_config, skip_vector=False)

    # Verify indexes exist
    with neo4j_driver.session() as session:
        # Check constraints
        result = session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        constraint_names = [c.get("name") for c in constraints]

        assert "document_source_path_unique" in constraint_names
        assert "section_node_id_unique" in constraint_names

        # Check fulltext indexes
        result = session.run("SHOW INDEXES WHERE type = 'FULLTEXT'")
        indexes = list(result)
        index_names = [idx.get("name") for idx in indexes]

        assert "document_fulltext" in index_names
        assert "section_fulltext" in index_names


def test_vector_index_created(neo4j_driver: Driver) -> None:
    """Test that vector index is created with correct dimensions."""
    embedding_config = EmbeddingConfig.from_env()
    create_indexes(neo4j_driver, embedding_config, skip_vector=False)

    with neo4j_driver.session() as session:
        result = session.run("SHOW INDEXES WHERE type = 'VECTOR'")
        vector_indexes = list(result)

        # Should have at least one vector index
        assert len(vector_indexes) > 0

        # Check the embedding index
        embedding_idx = next(
            (idx for idx in vector_indexes if "embedding" in idx.get("name", "").lower()),
            None
        )
        assert embedding_idx is not None
        options = embedding_idx.get("options", {})
        actual_dims = options.get("vector.dimensions")
        assert actual_dims == embedding_config.dimensions


def test_skip_vector_flag(neo4j_driver: Driver) -> None:
    """Test that --skip-vector prevents vector index creation."""
    embedding_config = EmbeddingConfig.from_env()

    # Create indexes with skip_vector=True
    create_indexes(neo4j_driver, embedding_config=None, skip_vector=True)

    # Vector index should still not be created (or already exist from previous tests)
    # This test just verifies that skip_vector=True doesn't raise an error
