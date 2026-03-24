"""Idempotent graph loader for pageindex documents."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from neo4j import Driver

from ...application.ports import EmbeddingPort
from ...domain.models.search import SearchDocumentIndex, SearchProfile, EmbeddingPayload
from ...config import EmbeddingConfig
from ...infrastructure.embeddings.factory import build_embedder


def _log(message: str, level: str = "INFO") -> None:
    """Log a message to stderr with a timestamp and level prefix.

    Args:
        message: The log message.
        level: Log level (INFO, WARNING, ERROR).
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] {level}: {message}", file=sys.stderr)


class PageIndexLoader:
    """Loads PageIndex documents into Neo4j with MERGE semantics for idempotency."""

    def __init__(self, driver: Driver, embedding_config: EmbeddingConfig | None = None, dry_run: bool = False):
        """Initialize the loader.

        Args:
            driver: Neo4j driver instance.
            embedding_config: EmbeddingConfig for embedding generation. None to skip embeddings.
            dry_run: If True, validate files without writing to Neo4j.
        """
        self.driver = driver
        self.embedding_config = embedding_config
        self.dry_run = dry_run
        self.embedder: EmbeddingPort | None = None

        # Build embedder when embedding configuration is present.
        # Vector-mode gating happens before the loader is constructed.
        if embedding_config is not None:
            try:
                self.embedder = build_embedder(embedding_config)
                _log(f"Loaded {embedding_config.provider} embedder (model: {embedding_config.model})")
            except ValueError as e:
                _log(f"Failed to load embedder: {e}", "WARNING")

    def load_all(self, pageindex_dir: str | Path) -> dict[str, Any]:
        """Load all .pageindex.json files from a directory.

        Args:
            pageindex_dir: Directory containing .pageindex.json files.

        Returns:
            Summary dict: {"total": int, "ok": int, "skipped": int, "inactive": int, "duration_ms": int}
        """
        pageindex_path = Path(pageindex_dir)
        if not pageindex_path.is_dir():
            raise ValueError(f"Directory not found: {pageindex_dir}")

        start_time = datetime.now()
        stats = {"total": 0, "ok": 0, "skipped": 0, "inactive": 0, "files": []}
        known_paths: set[str] = set()

        # Discover all .pageindex.json files
        pageindex_files = sorted(pageindex_path.glob("*.pageindex.json"))
        stats["total"] = len(pageindex_files)

        _log(f"Found {stats['total']} pageindex files in {pageindex_dir}")
        if self.dry_run:
            _log("DRY RUN MODE - no changes will be written to Neo4j")

        for pageindex_file in pageindex_files:
            try:
                with open(pageindex_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Parse as SearchDocumentIndex
                try:
                    doc_index = SearchDocumentIndex.from_dict(data)
                except (KeyError, ValueError) as e:
                    # Missing required field
                    result = {
                        "status": "skipped",
                        "source_path": str(pageindex_file.relative_to(pageindex_path.parent)),
                        "reason": f"invalid format: {e}",
                    }
                    stats["skipped"] += 1
                    stats["files"].append(result)
                    _log(f"Skipped {result['source_path']}: {result['reason']}", "WARNING")
                    print(json.dumps(result), flush=True)
                    continue

                # Track this path as seen
                relative_path = str(pageindex_file.relative_to(pageindex_path.parent))
                known_paths.add(relative_path)

                # Load into Neo4j
                if not self.dry_run:
                    nodes_created, nodes_updated, rels_created = self._load_document(doc_index, relative_path)
                    # Generate embeddings if enabled
                    if self.embedder:
                        self._generate_and_store_embeddings(doc_index)
                else:
                    nodes_created = nodes_updated = rels_created = 0

                result = {
                    "status": "ok",
                    "source_path": relative_path,
                    "nodes_created": nodes_created,
                    "nodes_updated": nodes_updated,
                    "relationships_created": rels_created,
                }
                stats["ok"] += 1
                stats["files"].append(result)
                print(json.dumps(result), flush=True)

            except json.JSONDecodeError as e:
                result = {
                    "status": "skipped",
                    "source_path": str(pageindex_file.relative_to(pageindex_path.parent)),
                    "reason": f"json parse error: {e}",
                }
                stats["skipped"] += 1
                stats["files"].append(result)
                print(json.dumps(result), flush=True)
            except Exception as e:
                result = {
                    "status": "skipped",
                    "source_path": str(pageindex_file.relative_to(pageindex_path.parent)),
                    "reason": f"unexpected error: {e}",
                }
                stats["skipped"] += 1
                stats["files"].append(result)
                print(json.dumps(result), flush=True)

        # Deactivate removed documents
        if not self.dry_run:
            inactive_count = self._deactivate_removed(known_paths)
            stats["inactive"] = inactive_count
            if inactive_count > 0:
                _log(f"Marked {inactive_count} document(s) as inactive (source files deleted)")

        # Calculate duration
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        stats["duration_ms"] = int(elapsed)

        # Print summary
        summary = {
            "summary": True,
            "total": stats["total"],
            "ok": stats["ok"],
            "skipped": stats["skipped"],
            "inactive": stats["inactive"],
            "duration_ms": stats["duration_ms"],
        }
        print(json.dumps(summary), flush=True)

        # Log summary
        _log(
            f"Load complete: {stats['ok']} succeeded, {stats['skipped']} skipped, "
            f"{stats['inactive']} inactivated in {stats['duration_ms']}ms"
        )

        return summary

    def _load_document(self, doc_index: SearchDocumentIndex, source_path: str) -> tuple[int, int, int]:
        """Load a single document into Neo4j.

        Args:
            doc_index: Parsed SearchDocumentIndex.
            source_path: Relative path to the source .pageindex.json file.

        Returns:
            Tuple of (nodes_created, nodes_updated, relationships_created) counts.
        """
        with self.driver.session() as session:
            # MERGE Document node
            session.run(
                """
                MERGE (d:Document {source_path: $source_path})
                SET
                    d.document_id = $document_id,
                    d.title = $title,
                    d.summary = $summary,
                    d.doc_description = $doc_description,
                    d.scope_label = $scope_label,
                    d.active = true,
                    d.ingested_at = datetime()
                """,
                source_path=source_path,
                document_id=doc_index.document_id,
                title=doc_index.title,
                summary=doc_index.summary,
                doc_description=doc_index.doc_description,
                scope_label=doc_index.scope_label,
            )

            # MERGE Section nodes and build section tree
            for section in doc_index.structure or []:
                self._merge_section(session, doc_index.document_id, section, parent_id=None)

            # MERGE metadata relationships
            search_profile = doc_index.search_profile or SearchProfile()

            if search_profile.issuer:
                session.run(
                    """
                    MERGE (org:Organization {name: $org_name})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:ISSUED_BY]->(org)
                    """,
                    org_name=search_profile.issuer,
                    document_id=doc_index.document_id,
                )

            if search_profile.region:
                session.run(
                    """
                    MERGE (r:Region {name: $region_name})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:COVERS_REGION]->(r)
                    """,
                    region_name=search_profile.region,
                    document_id=doc_index.document_id,
                )

            for city in search_profile.covered_cities or []:
                session.run(
                    """
                    MERGE (c:City {name: $city_name})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:COVERS_CITY]->(c)
                    """,
                    city_name=city,
                    document_id=doc_index.document_id,
                )

            for institution in search_profile.covered_institutions or []:
                session.run(
                    """
                    MERGE (i:Institution {name: $inst_name})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:COVERS_INSTITUTION]->(i)
                    """,
                    inst_name=institution,
                    document_id=doc_index.document_id,
                )

            if search_profile.academic_year:
                session.run(
                    """
                    MERGE (ay:AcademicYear {label: $ay_label})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:FOR_ACADEMIC_YEAR]->(ay)
                    """,
                    ay_label=search_profile.academic_year,
                    document_id=doc_index.document_id,
                )

            for benefit in search_profile.benefit_types or []:
                session.run(
                    """
                    MERGE (b:BenefitType {name: $benefit_name})
                    MERGE (d:Document {document_id: $document_id})
                    MERGE (d)-[:OFFERS_BENEFIT]->(b)
                    """,
                    benefit_name=benefit,
                    document_id=doc_index.document_id,
                )

        # Return dummy counts for now (could be enhanced with actual counts from MERGE results)
        return (1, 0, 0)

    def _merge_section(
        self,
        session: Any,
        document_id: str,
        section: dict[str, Any],
        parent_id: str | None,
        *,
        parent_path: str = "",
        order: int = 0,
    ) -> str:
        """Recursively merge a section and its subsections.

        Args:
            session: Neo4j session.
            document_id: Parent document ID.
            section: Section dict from structure.
            parent_id: Parent section node_id, or None for top-level.

        Returns:
            The node_id of the merged section.
        """
        node_id = section.get("node_id")
        if not node_id:
            raise ValueError("Section missing node_id")

        node_title = section.get("node_title") or section.get("title")
        line_number = section.get("line_number")
        if line_number is None:
            line_number = section.get("line_num")
        children = list(section.get("subsections", []) or section.get("nodes", []))
        current_path = section.get("path") or " > ".join(part for part in [parent_path, str(node_title or "").strip()] if part)
        depth = section.get("depth")
        if depth is None:
            depth = current_path.count(" > ")

        # MERGE Section node
        session.run(
            """
            MERGE (s:Section {node_id: $node_id})
            SET
                s.document_id = $document_id,
                s.node_title = $node_title,
                s.path = $path,
                s.text = $text,
                s.summary = $summary,
                s.line_number = $line_number,
                s.depth = $depth
            """,
            node_id=node_id,
            document_id=document_id,
            node_title=node_title,
            path=current_path,
            text=section.get("text"),
            summary=section.get("summary"),
            line_number=line_number,
            depth=depth,
        )

        # MERGE HAS_SECTION relationship (Document -> Section)
        session.run(
            """
            MERGE (d:Document {document_id: $document_id})
            MERGE (s:Section {node_id: $node_id})
            MERGE (d)-[:HAS_SECTION]->(s)
            """,
            document_id=document_id,
            node_id=node_id,
        )

        # MERGE PARENT_OF relationship if this is a subsection
        if parent_id:
            session.run(
                """
                MERGE (parent:Section {node_id: $parent_id})
                MERGE (child:Section {node_id: $node_id})
                MERGE (parent)-[:PARENT_OF {order: $order}]->(child)
                """,
                parent_id=parent_id,
                node_id=node_id,
                order=section.get("order", order),
            )

        # Recursively merge subsections
        for child_order, subsection in enumerate(children):
            self._merge_section(
                session,
                document_id,
                subsection,
                parent_id=node_id,
                parent_path=current_path,
                order=child_order,
            )

        return node_id

    def _generate_and_store_embeddings(self, doc_index: SearchDocumentIndex) -> None:
        """Generate embeddings for all sections and store them in Neo4j.

        Args:
            doc_index: SearchDocumentIndex with document and sections.
        """
        if not self.embedder:
            return

        # Collect all sections with their text
        sections_to_embed: list[tuple[str, str, str]] = []  # (node_id, text, section_title)

        def collect_sections(section: dict[str, Any]) -> None:
            """Recursively collect sections for embedding."""
            node_id = section.get("node_id")
            text = section.get("text", "")
            node_title = section.get("node_title") or section.get("title", "")

            if node_id and text:
                sections_to_embed.append((node_id, text, node_title))

            for subsection in list(section.get("subsections", []) or section.get("nodes", [])):
                collect_sections(subsection)

        # Collect all sections
        for section in doc_index.structure or []:
            collect_sections(section)

        if not sections_to_embed:
            return

        try:
            # Prepare embedding payloads
            embedding_texts = [text for _, text, _ in sections_to_embed]

            # Generate embeddings in batches
            embeddings = self.embedder.embed_documents(embedding_texts)

            # Store embeddings on Section nodes
            with self.driver.session() as session:
                for (node_id, text, node_title), embedding in zip(sections_to_embed, embeddings):
                    session.run(
                        """
                        MATCH (s:Section {node_id: $node_id})
                        SET
                            s.embedding = $embedding,
                            s.embedding_provider = $provider,
                            s.embedding_model = $model
                        """,
                        node_id=node_id,
                        embedding=embedding,
                        provider=self.embedder.provider_name,
                        model=self.embedding_config.model if self.embedding_config else None,
                    )

            _log(f"Generated and stored {len(embeddings)} embeddings for document {doc_index.document_id}")

        except Exception as e:
            _log(f"Failed to generate embeddings for {doc_index.document_id}: {e}", "WARNING")

    def _deactivate_removed(self, known_paths: set[str]) -> int:
        """Mark documents as inactive if their source file is no longer present.

        Args:
            known_paths: Set of source_path values currently seen in the directory.

        Returns:
            Count of documents marked inactive.
        """
        with self.driver.session() as session:
            # Find all active documents whose source_path is not in known_paths
            result = session.run(
                """
                MATCH (d:Document {active: true})
                WHERE NOT d.source_path IN $known_paths
                SET d.active = false
                RETURN count(d) as count
                """,
                known_paths=list(known_paths),
            )
            record = result.single()
            return record["count"] if record else 0
