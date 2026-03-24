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

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from docstruct.config import EmbeddingConfig, Neo4jConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.indexes import EmbeddingDimensionError, create_indexes


def main() -> int:
    """Main entry point."""
    if load_dotenv is not None:
        load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Create Neo4j indexes and constraints for hybrid search"
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip vector index creation (use when embeddings are disabled)",
    )
    args = parser.parse_args()

    try:
        neo4j_config = Neo4jConfig.from_env()
        embedding_config = EmbeddingConfig.from_env() if not args.skip_vector else None
        driver = build_driver(neo4j_config)

        try:
            print(f"Connecting to Neo4j at {neo4j_config.uri}...", file=sys.stderr)
            wait_for_neo4j(
                driver,
                max_retries=neo4j_config.readiness_retries,
                backoff_base=neo4j_config.readiness_backoff_base,
            )
            print("Connected to Neo4j", file=sys.stderr)

            print("Creating indexes and constraints...", file=sys.stderr)
            create_indexes(driver, embedding_config, skip_vector=args.skip_vector)

            if embedding_config:
                try:
                    from docstruct.infrastructure.neo4j.indexes import validate_vector_dimension

                    validate_vector_dimension(driver, embedding_config.dimensions)
                except EmbeddingDimensionError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 1

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

            print("\nAll indexes verified.")
            return 0
        finally:
            driver.close()

    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except EmbeddingDimensionError as exc:
        print(f"Dimension mismatch error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Neo4j connection error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
