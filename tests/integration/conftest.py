"""Pytest configuration and fixtures for integration tests."""

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest
from neo4j import Driver

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from docstruct.config import Neo4jConfig, EmbeddingConfig
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.indexes import create_indexes


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


@pytest.fixture(scope="session")
def seed_documents(neo4j_driver: Driver | None) -> Iterator[None]:
    """Session-scoped fixture that loads 5 test documents with known metadata into Neo4j.

    Creates:
    - 5 documents with different organizations, regions, and metadata
    - 2 sections per document for full-text and vector search
    - Pre-computed vectors for vector search (deterministic embeddings)

    Cleans up after all tests are done.
    """
    if neo4j_driver is None:
        return

    # Create indexes first
    try:
        embedding_config = EmbeddingConfig.from_env()
        create_indexes(neo4j_driver, embedding_config, skip_vector=False)
    except Exception:
        # Indexes might already exist, that's fine
        pass

    # Seeded test vectors (normalized, 1536-dim embeddings for text-embedding-3-small)
    # These are deterministic for reproducibility
    vectors = {
        "scholarship": [0.1] * 1536,  # Normalized to unit length conceptually
        "admission": [0.2] * 1536,
        "deadline": [0.3] * 1536,
        "registration": [0.4] * 1536,
        "funding": [0.5] * 1536,
    }

    # Normalize vectors to unit length
    for key in vectors:
        vec = vectors[key]
        magnitude = sum(x**2 for x in vec) ** 0.5
        vectors[key] = [x / magnitude for x in vec]

    with neo4j_driver.session() as session:
        # Document 1: MIT Scholarship Program
        session.run(
            """
            MERGE (org:Organization {name: 'Massachusetts Institute of Technology'})
            MERGE (region:Region {name: 'North America'})
            CREATE (d:Document {
                source_path: 'test/mit_scholarships.pageindex.json',
                document_id: 'doc_mit_scholarship',
                title: 'MIT Undergraduate Scholarship Program',
                summary: 'Comprehensive information about undergraduate scholarships at MIT',
                active: true,
                ingested_at: datetime(),
                organization: 'Massachusetts Institute of Technology',
                document_type: 'Policy'
            })
            CREATE (s1:Section {
                node_id: 'sec_mit_1',
                document_id: 'doc_mit_scholarship',
                node_title: 'Application Requirements',
                text: 'MIT scholarships require a completed application form, transcripts, and letters of recommendation from academic advisors.',
                depth: 1,
                embedding: $vec1
            })
            CREATE (s2:Section {
                node_id: 'sec_mit_2',
                document_id: 'doc_mit_scholarship',
                node_title: 'Scholarship Deadline',
                text: 'The application deadline for fall admission is March 15. Applicants must submit all materials before the deadline.',
                depth: 1,
                embedding: $vec2
            })
            CREATE (d)-[:HAS_SECTION]->(s1)
            CREATE (d)-[:HAS_SECTION]->(s2)
            CREATE (d)-[:BELONGS_TO_ORGANIZATION]->(org)
            CREATE (d)-[:LOCATED_IN_REGION]->(region)
            """
            , vec1=vectors["scholarship"], vec2=vectors["deadline"]
        )

        # Document 2: Harvard Admission Policy
        session.run(
            """
            MERGE (org:Organization {name: 'Harvard University'})
            MERGE (region:Region {name: 'North America'})
            CREATE (d:Document {
                source_path: 'test/harvard_admissions.pageindex.json',
                document_id: 'doc_harvard_admission',
                title: 'Harvard Admission Requirements and Timeline',
                summary: 'Official admission requirements and deadlines for Harvard College',
                active: true,
                ingested_at: datetime(),
                organization: 'Harvard University',
                document_type: 'Policy'
            })
            CREATE (s1:Section {
                node_id: 'sec_harvard_1',
                document_id: 'doc_harvard_admission',
                node_title: 'Admission Criteria',
                text: 'Harvard evaluates applicants holistically including academic achievement, extracurricular activities, and demonstrated leadership.',
                depth: 1,
                embedding: $vec1
            })
            CREATE (s2:Section {
                node_id: 'sec_harvard_2',
                document_id: 'doc_harvard_admission',
                node_title: 'Application Timeline',
                text: 'Applications must be submitted by January 1 for regular decision. Early action deadline is November 1.',
                depth: 1,
                embedding: $vec2
            })
            CREATE (d)-[:HAS_SECTION]->(s1)
            CREATE (d)-[:HAS_SECTION]->(s2)
            CREATE (d)-[:BELONGS_TO_ORGANIZATION]->(org)
            CREATE (d)-[:LOCATED_IN_REGION]->(region)
            """
            , vec1=vectors["admission"], vec2=vectors["deadline"]
        )

        # Document 3: Oxford Registration Process
        session.run(
            """
            MERGE (org:Organization {name: 'University of Oxford'})
            MERGE (region:Region {name: 'Europe'})
            CREATE (d:Document {
                source_path: 'test/oxford_registration.pageindex.json',
                document_id: 'doc_oxford_registration',
                title: 'Oxford Student Registration and Enrollment',
                summary: 'Step-by-step guide for student registration at Oxford University',
                active: true,
                ingested_at: datetime(),
                organization: 'University of Oxford',
                document_type: 'Procedure'
            })
            CREATE (s1:Section {
                node_id: 'sec_oxford_1',
                document_id: 'doc_oxford_registration',
                node_title: 'Registration Steps',
                text: 'New students must complete online registration, provide proof of identity, and pay enrollment fees.',
                depth: 1,
                embedding: $vec1
            })
            CREATE (s2:Section {
                node_id: 'sec_oxford_2',
                document_id: 'doc_oxford_registration',
                node_title: 'Enrollment Deadline',
                text: 'Registration must be completed by September 30 to ensure course allocation and accommodation booking.',
                depth: 1,
                embedding: $vec2
            })
            CREATE (d)-[:HAS_SECTION]->(s1)
            CREATE (d)-[:HAS_SECTION]->(s2)
            CREATE (d)-[:BELONGS_TO_ORGANIZATION]->(org)
            CREATE (d)-[:LOCATED_IN_REGION]->(region)
            """
            , vec1=vectors["registration"], vec2=vectors["deadline"]
        )

        # Document 4: Stanford Funding Opportunities
        session.run(
            """
            MERGE (org:Organization {name: 'Stanford University'})
            MERGE (region:Region {name: 'North America'})
            CREATE (d:Document {
                source_path: 'test/stanford_funding.pageindex.json',
                document_id: 'doc_stanford_funding',
                title: 'Stanford Financial Aid and Funding Sources',
                summary: 'Comprehensive guide to financial aid, grants, and funding opportunities at Stanford',
                active: true,
                ingested_at: datetime(),
                organization: 'Stanford University',
                document_type: 'Policy'
            })
            CREATE (s1:Section {
                node_id: 'sec_stanford_1',
                document_id: 'doc_stanford_funding',
                node_title: 'Merit Scholarships',
                text: 'Stanford offers full-ride merit scholarships to exceptional students. Applicants are automatically considered based on academic excellence.',
                depth: 1,
                embedding: $vec1
            })
            CREATE (s2:Section {
                node_id: 'sec_stanford_2',
                document_id: 'doc_stanford_funding',
                node_title: 'Financial Aid Application',
                text: 'Complete the Free Application for Federal Student Aid (FAFSA) and Stanford financial aid forms by December 1.',
                depth: 1,
                embedding: $vec2
            })
            CREATE (d)-[:HAS_SECTION]->(s1)
            CREATE (d)-[:HAS_SECTION]->(s2)
            CREATE (d)-[:BELONGS_TO_ORGANIZATION]->(org)
            CREATE (d)-[:LOCATED_IN_REGION]->(region)
            """
            , vec1=vectors["funding"], vec2=vectors["deadline"]
        )

        # Document 5: Cambridge General Information
        session.run(
            """
            MERGE (org:Organization {name: 'University of Cambridge'})
            MERGE (region:Region {name: 'Europe'})
            CREATE (d:Document {
                source_path: 'test/cambridge_info.pageindex.json',
                document_id: 'doc_cambridge_info',
                title: 'University of Cambridge: General Information',
                summary: 'Overview of Cambridge University programs, admissions, and student services',
                active: true,
                ingested_at: datetime(),
                organization: 'University of Cambridge',
                document_type: 'Information'
            })
            CREATE (s1:Section {
                node_id: 'sec_cambridge_1',
                document_id: 'doc_cambridge_info',
                node_title: 'Undergraduate Programs',
                text: 'Cambridge offers undergraduate programs in sciences, engineering, humanities, and social sciences with emphasis on tutorial education.',
                depth: 1,
                embedding: $vec1
            })
            CREATE (s2:Section {
                node_id: 'sec_cambridge_2',
                document_id: 'doc_cambridge_info',
                node_title: 'Application Timeline',
                text: 'Application deadline is October 15. Interviews typically occur in December with results announced in January.',
                depth: 1,
                embedding: $vec2
            })
            CREATE (d)-[:HAS_SECTION]->(s1)
            CREATE (d)-[:HAS_SECTION]->(s2)
            CREATE (d)-[:BELONGS_TO_ORGANIZATION]->(org)
            CREATE (d)-[:LOCATED_IN_REGION]->(region)
            """
            , vec1=vectors["admission"], vec2=vectors["deadline"]
        )

    yield

    # Cleanup after all tests
    with neo4j_driver.session() as session:
        session.run("MATCH (d:Document) WHERE d.source_path STARTS WITH 'test/' DETACH DELETE d")
        session.run("MATCH (s:Section) WHERE s.document_id STARTS WITH 'doc_' AND s.node_id STARTS WITH 'sec_' DETACH DELETE s")


@pytest.fixture(autouse=True)
def cleanup_neo4j(neo4j_driver: Driver | None) -> None:
    """Clean up test data before each test (optional).

    This is a placeholder for test isolation if needed.
    """
    if neo4j_driver is None:
        return
    # Could add cleanup logic here if tests create data that needs to be cleaned up
    yield
