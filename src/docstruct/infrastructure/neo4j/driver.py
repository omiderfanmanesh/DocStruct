"""Neo4j driver management and connection utilities."""

from __future__ import annotations

import time
from typing import Any

from neo4j import Driver, GraphDatabase, Auth

from ...config import Neo4jConfig


def build_driver(config: Neo4jConfig) -> Driver:
    """Build a Neo4j driver with the given configuration.

    Args:
        config: Neo4jConfig instance with connection parameters.

    Returns:
        A neo4j.Driver instance (caller is responsible for closing).

    Raises:
        ValueError: If config.uri or config.auth is invalid.
    """
    # Parse auth parameter
    if isinstance(config.auth, str):
        if config.auth.lower() == "none":
            auth = None
        else:
            raise ValueError(f"Invalid auth string: {config.auth}. Use 'none' or 'user/password' format")
    elif isinstance(config.auth, tuple):
        auth = Auth.basic(config.auth[0], config.auth[1])
    else:
        raise ValueError(f"auth must be string or tuple, got {type(config.auth)}")

    driver = GraphDatabase.driver(
        config.uri,
        auth=auth,
        max_pool_size=config.max_pool_size,
    )
    return driver


def wait_for_neo4j(
    driver: Driver,
    max_retries: int = 30,
    backoff_base: float = 1.0,
) -> bool:
    """Wait for Neo4j to become ready.

    Uses exponential backoff with a 10-second cap between retries.

    Args:
        driver: The Neo4j driver to test.
        max_retries: Maximum number of connection attempts.
        backoff_base: Base backoff multiplier (doubles each attempt, capped at 10s).

    Returns:
        True if Neo4j became ready within max_retries.

    Raises:
        RuntimeError: If Neo4j does not become ready after max_retries.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            # Test connection with a simple query
            with driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s, 8s, 10s, 10s, ...
                backoff = min(backoff_base * (2 ** (attempt - 1)), 10.0)
                time.sleep(backoff)
            continue

    # All retries exhausted
    error_msg = (
        f"Neo4j did not become ready after {max_retries} attempts.\n"
        f"  URI: {driver._uri}\n"
        f"  Last error: {last_error}\n"
        f"Troubleshooting:\n"
        f"  1. Check 'docker compose ps' — is neo4j container running and healthy?\n"
        f"  2. Check NEO4J_URI in your .env — should match the container port (default: bolt://localhost:7687)\n"
        f"  3. Check NEO4J_AUTH matches the docker-compose.yml setting\n"
        f"  4. Check Docker logs: 'docker compose logs neo4j'"
    )
    raise RuntimeError(error_msg)
