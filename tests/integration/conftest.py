"""Pytest configuration and fixtures for integration tests."""

import os
import sys
from pathlib import Path

import pytest
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import Neo4jConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j


@pytest.fixture(scope="session")
def neo4j_driver() -> Driver | None:
    """Session-scoped fixture providing a Neo4j driver.

    Skips all integration tests if NEO4J_URI is not set.

    Yields:
        A neo4j.Driver instance, or None if skipped.
    """
    neo4j_uri = os.getenv("NEO4J_URI")
    if not neo4j_uri:
        pytest.skip("NEO4J_URI environment variable not set; skipping Neo4j integration tests")
        return None

    try:
        config = Neo4jConfig.from_env()
        driver = build_driver(config)
        wait_for_neo4j(driver, max_retries=config.readiness_retries)
        yield driver
        driver.close()
    except Exception as e:
        pytest.skip(f"Could not connect to Neo4j: {e}")
        return None


@pytest.fixture(autouse=True)
def cleanup_neo4j(neo4j_driver: Driver | None) -> None:
    """Clean up test data before each test (optional).

    This is a placeholder for test isolation if needed.
    """
    if neo4j_driver is None:
        return
    # Could add cleanup logic here if tests create data that needs to be cleaned up
    yield
