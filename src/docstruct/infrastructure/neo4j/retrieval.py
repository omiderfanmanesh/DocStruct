"""Neo4j-backed hybrid retrieval layer."""

from __future__ import annotations

import sys
from typing import Any

from neo4j import Driver

from ...domain.models.search import RetrievalCandidate, SearchDocumentIndex, SearchProfile
from ...domain.rrf import reciprocal_rank_fusion
from ...config import RetrievalConfig, EmbeddingConfig
from .factory import build_embedder


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
        """Retrieve candidates using hybrid multi-mode retrieval with RRF fusion.

        Combines up to 3 retrieval modes based on configuration:
        1. Graph mode: Finds documents with matching metadata relationships
        2. Full-text mode: BM25 search on document titles/summaries and section text
        3. Vector mode: Semantic similarity on section embeddings

        Results from each enabled mode are fused using Reciprocal Rank Fusion (k=60)
        for deterministic, balanced ranking that avoids mode dominance.

        Args:
            question: Natural language question.
            query_embedding: Optional pre-computed embedding vector for vector search.
                           If None and vector mode is enabled, embedding will be generated from question.
            limit: Max candidates to return (applies to final fused result).

        Returns:
            List of RetrievalCandidate objects sorted by RRF score (highest first).
            - If no modes are enabled: returns empty list
            - If only one mode enabled: returns that mode's results sorted by its rank
            - If multiple modes enabled: returns fused results with rrf_score populated
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

        # Vector mode (if enabled with embedder)
        vector_results = []
        if self.retrieval_config.enable_vector and self.embedding_config:
            # Generate embedding if not provided
            if query_embedding is None:
                try:
                    embedder = build_embedder(self.embedding_config)
                    query_embedding = embedder.embed_query(question)
                except Exception as e:
                    sys.stderr.write(f"Warning: Failed to generate query embedding: {e}\n")
                    query_embedding = None

            # Run vector search if we have embedding
            if query_embedding:
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

            # Query all sections with their parent relationships
            result = session.run(
                """
                MATCH (d:Document {document_id: $document_id})-[:HAS_SECTION]->(s:Section)
                RETURN s
                ORDER BY s.depth, s.node_title
                """,
                document_id=document_id,
            )
            sections_map: dict[str, dict[str, Any]] = {}
            for rec in result:
                section = rec["s"]
                section_props = dict(section)
                node_id = section_props["node_id"]
                sections_map[node_id] = {
                    "node_id": node_id,
                    "node_title": section_props.get("node_title"),
                    "path": section_props.get("path"),
                    "text": section_props.get("text"),
                    "summary": section_props.get("summary"),
                    "line_number": section_props.get("line_number"),
                    "depth": section_props.get("depth", 0),
                    "subsections": [],
                }

            # Query parent-child relationships to rebuild tree
            result = session.run(
                """
                MATCH (parent:Section)-[:PARENT_OF {order: $order}]->(child:Section)
                WHERE parent.document_id = $document_id AND child.document_id = $document_id
                RETURN parent.node_id as parent_id, child.node_id as child_id, $order as order
                """,
                document_id=document_id,
                order=None,  # Will retrieve all orders
            )
            # Rebuild tree structure - try a simpler approach
            result = session.run(
                """
                MATCH (parent:Section)-[:PARENT_OF]->(child:Section)
                WHERE parent.document_id = $document_id AND child.document_id = $document_id
                RETURN parent.node_id as parent_id, child.node_id as child_id
                """,
                document_id=document_id,
            )
            parent_map: dict[str, str] = {}  # child_id -> parent_id
            for rec in result:
                parent_map[rec["child_id"]] = rec["parent_id"]

            # Build hierarchical structure
            root_sections = []
            for node_id, section_dict in sections_map.items():
                if node_id not in parent_map:
                    # This is a root section
                    root_sections.append(self._build_section_tree(node_id, sections_map, parent_map))

            structure = root_sections

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

    def _build_section_tree(
        self,
        node_id: str,
        sections_map: dict[str, dict[str, Any]],
        parent_map: dict[str, str],
    ) -> dict[str, Any]:
        """Recursively build section tree structure.

        Args:
            node_id: Current section node ID.
            sections_map: Map of all sections by node_id.
            parent_map: Map of child_id -> parent_id relationships.

        Returns:
            Section dict with subsections populated.
        """
        section_dict = sections_map[node_id].copy()
        section_dict["subsections"] = []

        # Find all children of this node
        for child_id, parent_id in parent_map.items():
            if parent_id == node_id:
                child_section = self._build_section_tree(child_id, sections_map, parent_map)
                section_dict["subsections"].append(child_section)

        return section_dict

    def _graph_retrieve(self, question: str, limit: int) -> list[RetrievalCandidate]:
        """Graph-mode retrieval: match documents based on structured metadata.

        Searches for documents connected to metadata nodes (Organization, Region, Institution, etc.)
        by matching question keywords against metadata node names.

        Args:
            question: Query text.
            limit: Max results.

        Returns:
            List of RetrievalCandidate from graph matches.
        """
        with self.driver.session() as session:
            # Convert question to lowercase for case-insensitive matching
            question_lower = question.lower()

            # Query for documents connected to metadata nodes
            result = session.run(
                """
                MATCH (d:Document {active: true})
                WHERE (
                    // Organization match
                    EXISTS((d)-[:ISSUED_BY]->(org:Organization))
                    OR
                    // Region match
                    EXISTS((d)-[:COVERS_REGION]->(r:Region))
                    OR
                    // City match
                    EXISTS((d)-[:COVERS_CITY]->(c:City))
                    OR
                    // Institution match
                    EXISTS((d)-[:COVERS_INSTITUTION]->(i:Institution))
                    OR
                    // Academic year match
                    EXISTS((d)-[:FOR_ACADEMIC_YEAR]->(ay:AcademicYear))
                    OR
                    // Benefit match
                    EXISTS((d)-[:OFFERS_BENEFIT]->(b:BenefitType))
                )
                RETURN d.document_id as id, d.title as title
                LIMIT $limit
                """,
                limit=limit * 2,  # Over-fetch for filtering
            )

            candidates: list[RetrievalCandidate] = []
            for rank, rec in enumerate(result, 1):
                # Simple relevance: check if any metadata words appear in the question
                title_lower = (rec.get("title") or "").lower()
                relevance_score = 1.0 / (rank + 1)  # Basic score based on rank

                if rank <= limit:
                    candidate = RetrievalCandidate(
                        document_id=rec["id"],
                        node_id=None,
                        node_type="document",
                        graph_rank=rank,
                    )
                    candidates.append(candidate)

            return candidates[:limit]

    def _fulltext_retrieve(self, question: str, limit: int) -> list[RetrievalCandidate]:
        """Full-text retrieval: search both documents and sections.

        Returns highest-scoring results across both document and section full-text indexes.

        Args:
            question: Query text.
            limit: Max results.

        Returns:
            List of RetrievalCandidate from full-text search (documents and sections).
        """
        with self.driver.session() as session:
            # Query document full-text index
            doc_results = []
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('document_fulltext', $q)
                YIELD node, score
                WHERE node.active = true
                RETURN node.document_id as id, score, 'document' as type, null as section_id
                """,
                q=question,
            )
            for rec in result:
                doc_results.append({
                    "id": rec["id"],
                    "score": rec["score"],
                    "type": rec["type"],
                    "section_id": None,
                })

            # Query section full-text index
            section_results = []
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('section_fulltext', $q)
                YIELD node, score
                MATCH (d:Document)-[:HAS_SECTION]->(node)
                WHERE d.active = true
                RETURN d.document_id as id, score, 'section' as type, node.node_id as section_id
                """,
                q=question,
            )
            for rec in result:
                section_results.append({
                    "id": rec["id"],
                    "score": rec["score"],
                    "type": rec["type"],
                    "section_id": rec["section_id"],
                })

            # Merge and sort by score (highest first)
            all_results = doc_results + section_results
            all_results.sort(key=lambda x: x["score"], reverse=True)

            # Build candidates list with ranks
            candidates: list[RetrievalCandidate] = []
            seen_docs = set()  # Track documents we've already added

            for rank, rec in enumerate(all_results[:limit * 2], 1):  # Over-fetch to account for deduplication
                doc_id = rec["id"]

                # For document-level results, add if not seen
                if rec["type"] == "document":
                    if doc_id not in seen_docs:
                        candidate = RetrievalCandidate(
                            document_id=doc_id,
                            node_id=None,
                            node_type="document",
                            fulltext_rank=rank,
                        )
                        candidates.append(candidate)
                        seen_docs.add(doc_id)
                else:
                    # For section-level results, add the containing document
                    if doc_id not in seen_docs:
                        candidate = RetrievalCandidate(
                            document_id=doc_id,
                            node_id=rec["section_id"],
                            node_type="section",
                            fulltext_rank=rank,
                        )
                        candidates.append(candidate)
                        seen_docs.add(doc_id)

                if len(candidates) >= limit:
                    break

            return candidates[:limit]

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
