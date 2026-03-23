#!/usr/bin/env python3
"""Create Neo4j indexes and constraints for the hybrid search feature.

Usage:
    python tools/create_neo4j_indexes.py [--skip-vector]

Exit codes:
    0: Success (all indexes created or already exist)
    1: Fatal error (connection failure, config error, dimension mismatch)
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docstruct.config import Neo4jConfig, EmbeddingConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.indexes import create_indexes, EmbeddingDimensionError


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create Neo4j indexes and constraints for hybrid search"
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip vector index creation (use when embeddings are disabled)"
    )
    args = parser.parse_args()

    try:
        # Load config
        neo4j_config = Neo4jConfig.from_env()
        embedding_config = EmbeddingConfig.from_env() if not args.skip_vector else None

        # Build driver
        driver = build_driver(neo4j_config)

        try:
            # Wait for readiness
            print(f"Connecting to Neo4j at {neo4j_config.uri}...", file=sys.stderr)
            wait_for_neo4j(driver, max_retries=neo4j_config.readiness_retries)
            print("✓ Connected to Neo4j", file=sys.stderr)

            # Create indexes
            print("Creating indexes and constraints...", file=sys.stderr)
            create_indexes(driver, embedding_config, skip_vector=args.skip_vector)

            # Validate vector dimension if embedding config present
            if embedding_config:
                try:
                    from docstruct.infrastructure.neo4j.indexes import validate_vector_dimension
                    validate_vector_dimension(driver, embedding_config.dimensions)
                except EmbeddingDimensionError as e:
                    print(f"ERROR: {e}", file=sys.stderr)
                    return 1

            # Print success output
            print("\nCreated constraint: document_source_path_unique")
            print("Created constraint: section_node_id_unique")
            print("Created constraint: org_name_unique")
            print("Created constraint: region_name_unique")
            print("Created constraint: city_name_unique")
            print("Created constraint: institution_name_unique")
            print("Created constraint: academic_year_label_unique")
            print("Created constraint: benefit_type_name_unique")
            print("\nCreated index: document_fulltext")
            print("Created index: section_fulltext")

            if not args.skip_vector and embedding_config:
                dims = embedding_config.dimensions
                provider = embedding_config.provider
                print(f"Created index: section_embedding (dimensions={dims}, provider={provider})")

            print("\n✓ All indexes verified.")
            return 0

        finally:
            driver.close()

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except EmbeddingDimensionError as e:
        print(f"Dimension mismatch error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Neo4j connection error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
