"""Integration tests for Neo4j connectivity and basic driver operations."""

import pytest
from neo4j import Driver


def test_driver_connects(neo4j_driver: Driver) -> None:
    """Test that the driver successfully connects to Neo4j."""
    assert neo4j_driver is not None
    assert neo4j_driver._uri is not None


def test_simple_query(neo4j_driver: Driver) -> None:
    """Test that a simple query can be executed."""
    with neo4j_driver.session() as session:
        result = session.run("RETURN 1 as value")
        record = result.single()
        assert record is not None
        assert record["value"] == 1


def test_node_creation_and_query(neo4j_driver: Driver) -> None:
    """Test creating and querying a test node."""
    with neo4j_driver.session() as session:
        # Create a test node
        session.run("CREATE (t:TestNode {name: $name})", name="connectivity_test")

        # Query the test node
        result = session.run("MATCH (t:TestNode {name: $name}) RETURN t.name", name="connectivity_test")
        record = result.single()
        assert record is not None
        assert record[0] == "connectivity_test"

        # Clean up
        session.run("MATCH (t:TestNode {name: $name}) DELETE t", name="connectivity_test")
