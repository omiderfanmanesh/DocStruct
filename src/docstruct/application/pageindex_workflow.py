"""PageIndex-backed indexing and document QA workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from docstruct.application.pageindex_search_graph import PageIndexSearchGraphRunner

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.application.ports import LLMPort
from docstruct.config import ContextConfig, EmbeddingConfig, Neo4jConfig, RetrievalConfig
from docstruct.domain.answer_quality import assess_answer_quality, guard_empty_context
from docstruct.domain.models import DocumentMetadata, SearchAnswer, SearchDocumentIndex, SearchTraceStep
from docstruct.domain.pageindex_search import (
    build_context_blocks,
    build_document_identity_terms,
    build_document_scope_label,
    build_search_profile,
    build_scope_clarification,
    choose_candidate_documents,
    fallback_node_matches,
    find_ambiguous_candidate_documents,
    question_has_scope_or_detail_hint,
    question_requests_multi_document_answer,
)
from docstruct.domain.query_validation import validate_query
from docstruct.infrastructure.cache import (
    cache_document,
    cache_result,
    get_cached_document,
    get_cached_result,
)
from docstruct.infrastructure.circuit_breaker import CircuitBreakerOpen, get_circuit_breaker
from docstruct.infrastructure.logging import log_stage, logger
from docstruct.infrastructure.metrics import Timer, calculate_cost, estimate_tokens, get_metrics
from docstruct.infrastructure.neo4j.driver import build_driver, wait_for_neo4j
from docstruct.infrastructure.neo4j.retrieval import Neo4jRetrieval
from docstruct.infrastructure.pageindex_adapter import build_markdown_tree


def _load_metadata_and_summary(extraction_json_path: str | None) -> tuple[DocumentMetadata | None, str | None]:
    if not extraction_json_path or not Path(extraction_json_path).exists():
        return None, None
    data = json.loads(Path(extraction_json_path).read_text(encoding="utf-8"))
    metadata_data = data.get("metadata")
    metadata = DocumentMetadata.from_dict(metadata_data) if metadata_data else None
    summary = data.get("summary")
    return metadata, summary


def _resolve_index_title(
    source: Path,
    tree: dict,
    metadata: DocumentMetadata | None,
) -> str:
    metadata_title = (metadata.title or "").strip() if metadata else ""
    if metadata_title and metadata_title.lower() not in {"unknown", "none", "null"}:
        return metadata_title
    return tree.get("doc_name", source.stem)


def build_search_index(
    markdown_path: str,
    output_path: str,
    *,
    extraction_json_path: str | None = None,
) -> SearchDocumentIndex:
    tree = build_markdown_tree(markdown_path)
    metadata, summary = _load_metadata_and_summary(extraction_json_path)
    source = Path(markdown_path)
    index = SearchDocumentIndex(
        document_id=source.stem,
        title=_resolve_index_title(source, tree, metadata),
        source_path=str(source),
        summary=summary,
        metadata=metadata,
        doc_description=tree.get("doc_description"),
        structure=list(tree.get("structure", [])),
    )
    index.search_profile = build_search_profile(index)
    index.scope_label = build_document_scope_label(index)
    index.identity_terms = build_document_identity_terms(index)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return index


def build_search_indexes(
    markdown_paths: list[str],
    output_dir: str,
    *,
    extraction_dir: str | None = None,
) -> list[SearchDocumentIndex]:
    indexes: list[SearchDocumentIndex] = []
    output_root = Path(output_dir)
    extraction_root = Path(extraction_dir) if extraction_dir else None
    for markdown_path in markdown_paths:
        source = Path(markdown_path)
        extraction_json_path = None
        if extraction_root:
            candidate = extraction_root / f"{source.stem}.json"
            if candidate.exists():
                extraction_json_path = str(candidate)
        indexes.append(
            build_search_index(
                markdown_path,
                str(output_root / f"{source.stem}.pageindex.json"),
                extraction_json_path=extraction_json_path,
            )
        )
    return indexes


def load_search_indexes(index_dir: str) -> list[SearchDocumentIndex]:
    root = Path(index_dir)
    if not root.exists():
        return []
    return [
        SearchDocumentIndex.from_dict(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(root.glob("*.pageindex.json"))
    ]


def _trace_value(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _trace_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_trace_value(item) for item in value]
    return str(value)


def _summarize_documents(documents: list[SearchDocumentIndex], *, limit: int = 4) -> list[dict[str, str | None]]:
    summary: list[dict[str, str | None]] = []
    for document in documents[:limit]:
        profile = build_search_profile(document)
        summary.append(
            {
                "document_id": document.document_id,
                "scope_label": build_document_scope_label(document),
                "region": profile.region,
                "issuer": profile.issuer,
            }
        )
    return summary


def _promote_documents(
    documents: list[SearchDocumentIndex],
    preferred_ids: list[str],
    *,
    limit: int,
) -> list[SearchDocumentIndex]:
    by_id = {document.document_id: document for document in documents}
    ordered: list[SearchDocumentIndex] = []
    for document_id in preferred_ids:
        document = by_id.get(document_id)
        if document is not None and document not in ordered:
            ordered.append(document)
    for document in documents:
        if document not in ordered:
            ordered.append(document)
    return ordered[:limit]


def _build_neo4j_retrieval() -> tuple[Neo4jRetrieval | None, object | None]:
    """Build a Neo4j retrieval adapter from environment configuration.

    Returns:
        Tuple of (retrieval_adapter, driver). Both values are None when Neo4j
        retrieval is not configured or cannot be initialized.
    """
    if not os.getenv("NEO4J_URI") or not os.getenv("NEO4J_AUTH"):
        return None, None

    driver = None
    try:
        neo4j_config = Neo4jConfig.from_env()
        retrieval_config = RetrievalConfig.from_env()

        embedding_config = None
        if retrieval_config.enable_vector:
            try:
                embedding_config = EmbeddingConfig.from_env()
            except ValueError as exc:
                print(
                    f"Warning: Neo4j vector retrieval disabled because embedding config is incomplete: {exc}",
                    file=sys.stderr,
                )

        driver = build_driver(neo4j_config)
        wait_for_neo4j(
            driver,
            max_retries=neo4j_config.readiness_retries,
            backoff_base=neo4j_config.readiness_backoff_base,
        )
        return Neo4jRetrieval(driver, retrieval_config, embedding_config=embedding_config), driver
    except Exception as exc:
        if driver is not None:
            driver.close()
        print(
            f"Warning: Neo4j retrieval unavailable, falling back to file-based indexes: {exc}",
            file=sys.stderr,
        )
        return None, None


def _candidate_documents_from_neo4j(
    neo4j_retrieval: Neo4jRetrieval,
    question: str,
    *,
    limit: int,
) -> list[SearchDocumentIndex]:
    """Resolve Neo4j retrieval candidates to SearchDocumentIndex objects."""
    documents: list[SearchDocumentIndex] = []
    seen_document_ids: set[str] = set()

    for candidate in neo4j_retrieval.retrieve_candidates(question, limit=limit):
        document_id = candidate.document_id
        if document_id in seen_document_ids:
            continue
        document = neo4j_retrieval.get_document_index(document_id)
        if document is not None:
            documents.append(document)
            seen_document_ids.add(document_id)

    return documents


def _load_search_indexes_from_neo4j(neo4j_retrieval: Neo4jRetrieval) -> list[SearchDocumentIndex]:
    """Load all active documents from Neo4j as SearchDocumentIndex objects."""
    indexes: list[SearchDocumentIndex] = []
    for document_id in neo4j_retrieval.list_active_document_ids():
        document = neo4j_retrieval.get_document_index(document_id)
        if document is not None:
            indexes.append(document)
    return indexes


def _neo4j_seed_node_ids(
    neo4j_retrieval: Neo4jRetrieval | None,
    question: str,
    document_ids: list[str],
    *,
    limit: int = 8,
) -> dict[str, list[str]]:
    if neo4j_retrieval is None or not document_ids:
        return {}

    seed_nodes: dict[str, list[str]] = {}
    for candidate in neo4j_retrieval.retrieve_candidates(question, limit=max(limit, len(document_ids) * 2)):
        if candidate.document_id not in document_ids:
            continue
        candidate_seed_node_ids = list(candidate.source_node.get("seed_node_ids", []))
        if candidate.node_id and candidate.node_id not in candidate_seed_node_ids:
            candidate_seed_node_ids.insert(0, candidate.node_id)
        for node_id in candidate_seed_node_ids:
            if not node_id:
                continue
            seed_nodes.setdefault(candidate.document_id, [])
            if node_id not in seed_nodes[candidate.document_id]:
                seed_nodes[candidate.document_id].append(node_id)
    return seed_nodes


def _populate_answer_metrics(
    answer: SearchAnswer,
    question: str,
    query_timer: Timer | None,
) -> SearchAnswer:
    """Add execution metrics to a SearchAnswer."""
    if query_timer is None:
        return answer
    # Use elapsed_ms property instead of stop() to avoid multiple stops
    query_time_ms = query_timer.elapsed_ms
    answer.execution_time_seconds = query_time_ms / 1000.0
    answer.tokens_used = estimate_tokens(len(question), len(answer.answer))
    answer.estimated_cost_usd = calculate_cost(answer.tokens_used)
    return answer


def answer_question(
    question: str,
    index_dir: str,
    client: LLMPort,
    *,
    retrieval_backend: str = "auto",
) -> SearchAnswer:
    metrics = get_metrics()
    metrics.record_query()
    query_timer = Timer().start()

    if retrieval_backend not in {"auto", "pageindex", "neo4j"}:
        raise ValueError(
            "retrieval_backend must be one of: auto, pageindex, neo4j"
        )

    # --- Query validation ---
    validation = validate_query(question)
    if not validation.is_valid:
        logger.warning(
            "Query rejected: %s (injection=%s)",
            validation.rejection_reason,
            validation.injection_detected,
        )
        rejection_answer = validation.rejection_reason or "Invalid query."
        answer = SearchAnswer(
            question=question,
            answer=rejection_answer,
            document_ids=[],
            retrieval_notes=f"Query validation failed: {validation.rejection_reason}",
        )
        return _populate_answer_metrics(answer, question, query_timer)
    question = validation.sanitized_query

    # --- Result cache check ---
    cached = get_cached_result(question, retrieval_backend)
    if cached is not None:
        logger.info("Cache hit for query: %s", question[:80])
        # Update execution time for cache hit (should be minimal)
        return _populate_answer_metrics(cached, question, query_timer)

    use_neo4j = retrieval_backend in {"auto", "neo4j"}
    neo4j_retrieval = None
    neo4j_driver = None
    if use_neo4j:
        try:
            neo4j_breaker = get_circuit_breaker("neo4j")
            neo4j_retrieval, neo4j_driver = neo4j_breaker.call(_build_neo4j_retrieval)
        except CircuitBreakerOpen as exc:
            logger.warning("Neo4j circuit breaker open: %s", exc)
            neo4j_retrieval, neo4j_driver = None, None
        except Exception:
            neo4j_retrieval, neo4j_driver = None, None
    if retrieval_backend == "neo4j" and neo4j_retrieval is None:
        raise ValueError("Neo4j retrieval was requested, but Neo4j is not available.")

    active_retrieval_backend = "neo4j" if neo4j_retrieval is not None else "pageindex"
    try:
        indexes = load_search_indexes(index_dir)
        if not indexes and retrieval_backend == "auto" and neo4j_retrieval is not None:
            indexes = _load_search_indexes_from_neo4j(neo4j_retrieval)
        if not indexes:
            raise ValueError(f"No PageIndex search indexes found in {index_dir}")

        trace: list[SearchTraceStep] = []

        def add_trace(stage: str, message: str, **details: object) -> None:
            trace.append(
                SearchTraceStep(
                    stage=stage,
                    message=message,
                    details={key: _trace_value(value) for key, value in details.items()},
                )
            )

        with log_stage("load_indexes", retrieval_backend=active_retrieval_backend):
            add_trace(
                "load_indexes",
                "Loaded search indexes.",
                index_dir=index_dir,
                count=len(indexes),
                documents=_summarize_documents(indexes),
                requested_retrieval_backend=retrieval_backend,
                retrieval_backend=active_retrieval_backend,
            )

        multi_document_intent = question_requests_multi_document_answer(question)
        add_trace(
            "intent_detection",
            "Detected user intent for document scope.",
            multi_document_intent=multi_document_intent,
        )

        if neo4j_retrieval is not None:
            initial_candidates = _candidate_documents_from_neo4j(neo4j_retrieval, question, limit=6)
            if not initial_candidates:
                initial_candidates = choose_candidate_documents(question, indexes, limit=6)
        else:
            initial_candidates = choose_candidate_documents(question, indexes, limit=6)
        add_trace(
            "initial_ranking",
            "Ranked initial candidate documents from the original question.",
            question=question,
            candidates=_summarize_documents(initial_candidates, limit=6),
            retrieval_backend=active_retrieval_backend,
        )
        ambiguous_candidates = find_ambiguous_candidate_documents(question, initial_candidates)
        if ambiguous_candidates and not question_has_scope_or_detail_hint(question):
            clarification = build_scope_clarification(question, ambiguous_candidates)
            if clarification:
                metrics.record_clarification()
                add_trace(
                    "clarification_gate",
                    "Stopped early because the question is too generic across multiple document scopes.",
                    ambiguous_candidates=_summarize_documents(ambiguous_candidates),
                    clarifying_question=clarification,
                )
                answer = SearchAnswer(
                    question=question,
                    answer=clarification,
                    document_ids=[],
                    retrieval_notes="Question is generic and matches multiple document scopes.",
                    needs_clarification=True,
                    clarifying_question=clarification,
                    trace=trace,
                )
                return _populate_answer_metrics(answer, question, query_timer)

        result = PageIndexSearchGraphRunner(
            client,
            add_trace=add_trace,
            summarize_documents=_summarize_documents,
            neo4j_retrieval=neo4j_retrieval,
        ).run(
            question=question,
            indexes=indexes,
            multi_document_intent=multi_document_intent,
        )
        result.trace = trace

        # --- Answer quality assessment ---
        _apply_quality_assessment(result, trace, add_trace, metrics)

        # --- Cache the result ---
        if not result.needs_clarification:
            cache_result(question, retrieval_backend, result)

        # --- Record metrics ---
        query_time_ms = query_timer.stop()
        metrics.record_stage("total_query", query_time_ms)

        # --- Populate execution metrics on the result ---
        result = _populate_answer_metrics(result, question, query_timer)

        return result
    finally:
        if neo4j_driver is not None:
            neo4j_driver.close()


def _apply_quality_assessment(
    result: SearchAnswer,
    trace: list[SearchTraceStep],
    add_trace,
    metrics,
) -> None:
    """Run answer quality checks and attach metadata to the result."""
    # Extract contexts from trace for quality check
    context_step = next(
        (step for step in trace if step.stage == "context_building"),
        None,
    )
    context_count = context_step.details.get("context_count", 0) if context_step else 0

    # Build citation dicts for quality check
    citation_dicts = [c.to_dict() for c in result.citations]

    # We use a lightweight quality check based on available data
    quality = assess_answer_quality(
        answer=result.answer,
        citations=citation_dicts,
        contexts=citation_dicts,  # Use citations as proxy for context check
        question=result.question,
    )

    metrics.record_confidence(quality.confidence_score)
    if quality.warnings:
        metrics.record_quality_warning()

    add_trace(
        "quality_assessment",
        f"Answer quality: {quality.confidence_label} (score={quality.confidence_score})",
        confidence_score=quality.confidence_score,
        confidence_label=quality.confidence_label,
        has_grounded_citations=quality.has_grounded_citations,
        citation_coverage=quality.citation_coverage,
        potential_hallucination=quality.potential_hallucination,
        hallucination_indicators=quality.hallucination_indicators[:3],
        warnings=quality.warnings[:3],
    )
