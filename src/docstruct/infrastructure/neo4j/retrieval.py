"""Neo4j-backed hybrid retrieval layer."""

from __future__ import annotations

import sys
from typing import Any

from neo4j import Driver

from ...domain.models.search import RetrievalCandidate, SearchDocumentIndex, SearchProfile
from ...domain.rrf import reciprocal_rank_fusion
from ...config import RetrievalConfig, EmbeddingConfig


class Neo4jRetrieval:
    """Neo4j-backed retrieval implementing Neo4jRetrievalPort."""

    def __init__(
        self,
        driver: Driver,
        retrieval_config: RetrievalConfig,
        embedding_config: EmbeddingConfig | None = None,
    ):
        """Initialize retrieval layer.

        Args:
            driver: Neo4j driver instance.
            retrieval_config: RetrievalConfig with feature flags and limits.
            embedding_config: EmbeddingConfig for vector mode (optional).
        """
        self.driver = driver
        self.retrieval_config = retrieval_config
        self.embedding_config = embedding_config

    def retrieve_candidates(
        self,
        question: str,
        query_embedding: list[float] | None = None,
        *,
        limit: int = 6,
    ) -> list[RetrievalCandidate]:
        """Retrieve candidates using graph, full-text, and optional vector search.

        Args:
            question: Natural language question.
            query_embedding: Optional embedding vector for vector search.
            limit: Max candidates to return.

        Returns:
            List of RetrievalCandidate objects sorted by fused score.
        """
        # Collect ranked lists from enabled modes
        ranked_lists: list[list[str]] = []

        # Graph mode: relationship-based retrieval
        if self.retrieval_config.enable_graph:
            graph_results = self._graph_retrieve(question, limit)
            if graph_results:
                ranked_lists.append([cand.document_id for cand in graph_results])

        # Full-text mode
        if self.retrieval_config.enable_fulltext:
            fulltext_results = self._fulltext_retrieve(question, limit)
            if fulltext_results:
                ranked_lists.append([cand.document_id for cand in fulltext_results])

        # Vector mode (if embedding provided and enabled)
        if (
            self.retrieval_config.enable_vector
            and query_embedding
            and self.embedding_config
        ):
            vector_results = self._vector_retrieve(question, query_embedding, limit)
            if vector_results:
                ranked_lists.append([cand.document_id for cand in vector_results])

        # Fuse rankings using RRF
        fused_scores = reciprocal_rank_fusion(ranked_lists, k=60, limit=limit)

        # Build final candidate list with fused scores
        candidates: list[RetrievalCandidate] = []
        for doc_id, rrf_score in fused_scores:
            candidate = RetrievalCandidate(
                document_id=doc_id,
                node_id=None,  # Document-level for now
                node_type="document",
                rrf_score=rrf_score,
            )
            candidates.append(candidate)

        return candidates[:limit]

    def get_document_index(self, document_id: str) -> SearchDocumentIndex | None:
        """Retrieve and reconstruct a full SearchDocumentIndex from Neo4j.

        Args:
            document_id: The document ID.

        Returns:
            SearchDocumentIndex instance, or None if not found or inactive.
        """
        with self.driver.session() as session:
            # Query document
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id, active: true})
                RETURN d
                """,
                document_id=document_id,
            )
            record = result.single()
            if not record:
                return None

            doc_node = record["d"]
            doc_props = dict(doc_node)

            # Query sections
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:HAS_SECTION]->(s:Section)
                OPTIONAL MATCH (s)-[:PARENT_OF]->(child:Section)
                RETURN s, collect(child) as children
                ORDER BY s.depth, s.node_title
                """,
                document_id=document_id,
            )
            sections_map: dict[str, dict[str, Any]] = {}
            for rec in result:
                section = rec["s"]
                section_props = dict(section)
                sections_map[section_props["node_id"]] = {
                    "node_id": section_props["node_id"],
                    "node_title": section_props.get("node_title"),
                    "path": section_props.get("path"),
                    "text": section_props.get("text"),
                    "summary": section_props.get("summary"),
                    "line_number": section_props.get("line_number"),
                    "depth": section_props.get("depth", 0),
                    "subsections": [],
                }

            # Rebuild section tree (simple flat structure for now)
            structure = list(sections_map.values())

            # Query search profile (metadata relationships)
            search_profile = SearchProfile()

            # Query organization (issuer)
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:ISSUED_BY]->(org:Organization)
                RETURN org.name as name
                """,
                document_id=document_id,
            )
            record = result.single()
            if record:
                search_profile.issuer = record["name"]

            # Query region
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:COVERS_REGION]->(r:Region)
                RETURN r.name as name
                """,
                document_id=document_id,
            )
            record = result.single()
            if record:
                search_profile.region = record["name"]

            # Query cities
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:COVERS_CITY]->(c:City)
                RETURN c.name as name
                """,
                document_id=document_id,
            )
            search_profile.covered_cities = [rec["name"] for rec in result]

            # Query institutions
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:COVERS_INSTITUTION]->(i:Institution)
                RETURN i.name as name
                """,
                document_id=document_id,
            )
            search_profile.covered_institutions = [rec["name"] for rec in result]

            # Query academic year
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:FOR_ACADEMIC_YEAR]->(ay:AcademicYear)
                RETURN ay.label as label
                """,
                document_id=document_id,
            )
            record = result.single()
            if record:
                search_profile.academic_year = record["label"]

            # Query benefits
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:OFFERS_BENEFIT]->(b:BenefitType)
                RETURN b.name as name
                """,
                document_id=document_id,
            )
            search_profile.benefit_types = [rec["name"] for rec in result]

            # Construct SearchDocumentIndex
            return SearchDocumentIndex(
                document_id=doc_props["document_id"],
                title=doc_props["title"],
                source_path=doc_props["source_path"],
                summary=doc_props.get("summary"),
                doc_description=doc_props.get("doc_description"),
                scope_label=doc_props.get("scope_label"),
                search_profile=search_profile,
                structure=structure,
            )

    def list_active_document_ids(self) -> list[str]:
        """List all active document IDs.

        Returns:
            List of document IDs.
        """
        with self.driver.session() as session:
            result = session.run("MATCH (d:Document {active: true}) RETURN d.document_id as id")
            return [rec["id"] for rec in result]

    def _graph_retrieve(self, question: str, limit: int) -> list[RetrievalCandidate]:
        """Graph-mode retrieval: match documents based on structured metadata.

        For now, this is a placeholder that returns empty results.
        In a real implementation, this would parse the question for metadata hints
        (region, organization, institution, academic year, benefits) and match documents.

        Args:
            question: Query text.
            limit: Max results.

        Returns:
            List of RetrievalCandidate from graph matches.
        """
        # Placeholder: return empty for now
        return []

    def _fulltext_retrieve(self, question: str, limit: int) -> list[RetrievalCandidate]:
        """Full-text retrieval: search document and section text.

        Args:
            question: Query text.
            limit: Max results.

        Returns:
            List of RetrievalCandidate from full-text search.
        """
        with self.driver.session() as session:
            # Query document full-text index
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('document_fulltext', $q)
                YIELD node, score
                WHERE node.active = true
                RETURN node.document_id as id, score, 'document' as type
                LIMIT $limit
                """,
                q=question,
                limit=limit,
            )
            candidates: list[RetrievalCandidate] = []
            for rank, rec in enumerate(result, 1):
                candidate = RetrievalCandidate(
                    document_id=rec["id"],
                    node_id=None,
                    node_type=rec["type"],
                    fulltext_rank=rank,
                )
                candidates.append(candidate)

            return candidates

    def _vector_retrieve(
        self,
        question: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievalCandidate]:
        """Vector retrieval: semantic similarity search on section embeddings.

        Args:
            question: Query text (for context only; embedding already provided).
            query_embedding: Query embedding vector.
            limit: Max results.

        Returns:
            List of RetrievalCandidate from vector search.
        """
        if not query_embedding or not self.embedding_config:
            return []

        with self.driver.session() as session:
            # Query vector index for similar sections
            result = session.run(
                """
                CALL db.index.vector.queryNodes('section_embedding', $k, $queryVector)
                YIELD node, score
                MATCH (d:Document)-[:HAS_SECTION]->(node)
                WHERE d.active = true
                RETURN d.document_id as id, 'document' as type, score
                LIMIT $limit
                """,
                queryVector=query_embedding,
                k=limit,
                limit=limit,
            )
            candidates: list[RetrievalCandidate] = []
            for rank, rec in enumerate(result, 1):
                candidate = RetrievalCandidate(
                    document_id=rec["id"],
                    node_id=None,
                    node_type=rec["type"],
                    vector_rank=rank,
                )
                candidates.append(candidate)

            return candidates
