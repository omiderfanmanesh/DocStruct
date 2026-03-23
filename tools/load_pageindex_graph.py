#!/usr/bin/env python3
"""Load PageIndex documents into Neo4j graph.

Usage:
    python tools/load_pageindex_graph.py [--pageindex-dir <path>] [--dry-run] [--reset-inactive]

Options:
    --pageindex-dir     Directory containing .pageindex.json files (default: output/03_pageindex)
    --dry-run          Validate files without writing to Neo4j
    --reset-inactive   Re-activate previously inactive documents if source file is present again

Exit codes:
    0: All files processed successfully
    1: Fatal error (Neo4j connection, config)
    2: Partial failure (some files skipped)
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docstruct.config import Neo4jConfig, EmbeddingConfig, RetrievalConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.loader import PageIndexLoader


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Load pageindex documents into Neo4j"
    )
    parser.add_argument(
        "--pageindex-dir",
        default="output/03_pageindex",
        help="Directory containing .pageindex.json files (default: output/03_pageindex)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files without writing to Neo4j"
    )
    parser.add_argument(
        "--reset-inactive",
        action="store_true",
        help="Re-activate previously inactive documents if source file is present"
    )
    args = parser.parse_args()

    try:
        # Load config
        neo4j_config = Neo4jConfig.from_env()

        # Try to load embedding config; if it fails, set to None
        embedding_config = None
        try:
            retrieval_config = RetrievalConfig.from_env()
            if retrieval_config.enable_vector:
                embedding_config = EmbeddingConfig.from_env()
        except ValueError as e:
            print(f"Warning: Could not load embedding config: {e}", file=sys.stderr)

        # Build driver
        driver = build_driver(neo4j_config)

        try:
            # Wait for readiness
            print(f"Connecting to Neo4j at {neo4j_config.uri}...", file=sys.stderr)
            wait_for_neo4j(driver, max_retries=neo4j_config.readiness_retries)
            print("✓ Connected to Neo4j", file=sys.stderr)

            # Create loader and load documents
            print(f"Loading pageindex files from {args.pageindex_dir}...", file=sys.stderr)
            loader = PageIndexLoader(driver, embedding_config=embedding_config, dry_run=args.dry_run)
            summary = loader.load_all(args.pageindex_dir)

            # Determine exit code
            if summary["skipped"] > 0:
                print(f"\n⚠ Partial failure: {summary['skipped']} file(s) skipped", file=sys.stderr)
                return 2
            else:
                print(f"\n✓ Successfully loaded {summary['ok']} file(s)", file=sys.stderr)
                return 0

        finally:
            driver.close()

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Neo4j connection error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
