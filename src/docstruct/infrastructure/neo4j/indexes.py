"""Neo4j index and constraint management."""

from __future__ import annotations

from neo4j import Driver

from ...config import EmbeddingConfig
from ...domain.exceptions import EmbeddingDimensionError


def create_indexes(driver: Driver, embedding_config: EmbeddingConfig | None = None, skip_vector: bool = False) -> None:
    """Create all required Neo4j constraints and indexes.

    Uses IF NOT EXISTS clauses so this is safe to run multiple times.

    Args:
        driver: Neo4j driver instance.
        embedding_config: EmbeddingConfig for vector index dimension. Required unless skip_vector=True.
        skip_vector: If True, skip vector index creation.

    Raises:
        ValueError: If skip_vector=False and embedding_config is None.
    """
    if not skip_vector and embedding_config is None:
        raise ValueError("embedding_config required when skip_vector=False")

    with driver.session() as session:
        # === CONSTRAINTS ===

        # Document unique constraint on source_path
        session.run(
            "CREATE CONSTRAINT document_source_path_unique IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.source_path IS UNIQUE"
        )

        # Section unique constraint on node_id
        session.run(
            "CREATE CONSTRAINT section_node_id_unique IF NOT EXISTS "
            "FOR (s:Section) REQUIRE s.node_id IS UNIQUE"
        )

        # Organization unique constraint on name
        session.run(
            "CREATE CONSTRAINT org_name_unique IF NOT EXISTS "
            "FOR (o:Organization) REQUIRE o.name IS UNIQUE"
        )

        # Region unique constraint on name
        session.run(
            "CREATE CONSTRAINT region_name_unique IF NOT EXISTS "
            "FOR (r:Region) REQUIRE r.name IS UNIQUE"
        )

        # City unique constraint on name
        session.run(
            "CREATE CONSTRAINT city_name_unique IF NOT EXISTS "
            "FOR (c:City) REQUIRE c.name IS UNIQUE"
        )

        # Institution unique constraint on name
        session.run(
            "CREATE CONSTRAINT institution_name_unique IF NOT EXISTS "
            "FOR (i:Institution) REQUIRE i.name IS UNIQUE"
        )

        # AcademicYear unique constraint on label
        session.run(
            "CREATE CONSTRAINT academic_year_label_unique IF NOT EXISTS "
            "FOR (a:AcademicYear) REQUIRE a.label IS UNIQUE"
        )

        # BenefitType unique constraint on name
        session.run(
            "CREATE CONSTRAINT benefit_type_name_unique IF NOT EXISTS "
            "FOR (b:BenefitType) REQUIRE b.name IS UNIQUE"
        )

        # === FULLTEXT INDEXES ===

        # Document fulltext index
        session.run(
            "CREATE FULLTEXT INDEX document_fulltext IF NOT EXISTS "
            "FOR (d:Document) ON EACH [d.title, d.summary, d.scope_label, d.doc_description]"
        )

        # Section fulltext index
        session.run(
            "CREATE FULLTEXT INDEX section_fulltext IF NOT EXISTS "
            "FOR (s:Section) ON EACH [s.text, s.node_title, s.path, s.summary]"
        )

        # === VECTOR INDEX ===

        if not skip_vector and embedding_config:
            vector_dims = embedding_config.dimensions
            session.run(
                f"CREATE VECTOR INDEX section_embedding IF NOT EXISTS "
                f"FOR (s:Section) ON s.embedding "
                f"OPTIONS {{ vector.dimensions: {vector_dims}, vector.similarity_function: 'cosine' }}"
            )


def validate_vector_dimension(driver: Driver, expected_dims: int) -> None:
    """Validate that the vector index matches the expected dimensionality.

    Args:
        driver: Neo4j driver instance.
        expected_dims: Expected embedding dimension.

    Raises:
        EmbeddingDimensionError: If the vector index exists but has a different dimension.
    """
    with driver.session() as session:
        # Query SHOW INDEXES to find the vector index
        result = session.run("SHOW INDEXES WHERE type = 'VECTOR'")
        records = list(result)

        for record in records:
            index_name = record.get("name")
            if "embedding" in index_name.lower():
                # Extract dimensionality from options
                # The options are returned as a map with 'vector.dimensions' key
                options = record.get("options", {})
                actual_dims = options.get("vector.dimensions")

                if actual_dims and actual_dims != expected_dims:
                    raise EmbeddingDimensionError(
                        f"Vector index dimension {actual_dims} does not match "
                        f"provider dimension {expected_dims}. "
                        f"Drop the vector index and recreate it with matching dimensions, "
                        f"or switch EMBEDDING_PROVIDER and EMBEDDING_MODEL back to the provider used when the index was created."
                    )
                break
