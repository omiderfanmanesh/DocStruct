"""PageIndex-backed indexing and document QA workflow."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from docstruct.application.pageindex_search_graph import PageIndexSearchGraphRunner
except ImportError:  # pragma: no cover
    PageIndexSearchGraphRunner = None

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.application.ports import LLMPort
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


def _answer_question_without_langgraph(
    question: str,
    indexes: list[SearchDocumentIndex],
    client: LLMPort,
    *,
    multi_document_intent: bool,
    trace: list[SearchTraceStep],
    add_trace,
) -> SearchAnswer:
    add_trace(
        "workflow_runtime",
        "LangGraph is not installed in this environment, so the workflow is using the built-in sequential fallback.",
    )
    agent = PageIndexSearchAgent(client)
    effective_question = question
    rewrite_note = None
    inferred_document_ids: list[str] = []
    try:
        effective_question, rewrite_note, inferred_document_ids = agent.rewrite_question(question, indexes)
        add_trace(
            "rewrite_question",
            "Rewrote the question for retrieval.",
            original_question=question,
            rewritten_question=effective_question,
            reasoning=rewrite_note,
            inferred_document_ids=inferred_document_ids,
        )
    except Exception:
        effective_question, rewrite_note, inferred_document_ids = question, None, []
        add_trace(
            "rewrite_question",
            "Question rewrite failed, so the original question will be used.",
            original_question=question,
        )
    if effective_question != question:
        rewrite_note = " | ".join(
            note
            for note in [
                f"Rewrote question for retrieval: {effective_question}",
                rewrite_note,
            ]
            if note
        )

    candidate_documents = choose_candidate_documents(effective_question, indexes, limit=6)
    if inferred_document_ids:
        candidate_documents = _promote_documents(candidate_documents, inferred_document_ids, limit=6)
    add_trace(
        "candidate_ranking",
        "Ranked candidate documents for the effective retrieval question.",
        effective_question=effective_question,
        candidates=_summarize_documents(candidate_documents, limit=6),
    )
    heuristic_clarification = build_scope_clarification(effective_question, candidate_documents[:4])

    try:
        selection = agent.select_documents(effective_question, candidate_documents)
        add_trace(
            "document_selection",
            "Selected document scopes for answer generation.",
            effective_question=effective_question,
            selected_document_ids=selection.document_ids,
            needs_clarification=selection.needs_clarification,
            clarifying_question=selection.clarifying_question,
            reasoning=selection.thinking,
        )
    except Exception:
        selection = None
        add_trace(
            "document_selection",
            "Document selection failed, so the workflow will fall back to heuristic candidates.",
            effective_question=effective_question,
        )

    if selection and selection.needs_clarification:
        clarifying_question = selection.clarifying_question or heuristic_clarification
        return SearchAnswer(
            question=question,
            answer=clarifying_question or "I need the university, region, or issuing organization before I can answer safely.",
            document_ids=[],
            retrieval_notes=" | ".join(note for note in [rewrite_note, selection.thinking] if note) or None,
            needs_clarification=True,
            clarifying_question=clarifying_question,
            trace=trace,
        )

    selected_document_ids = selection.document_ids if selection else []
    selection_notes = selection.thinking if selection else None
    document_map = {document.document_id: document for document in candidate_documents}
    selected_documents = [
        document_map[document_id]
        for document_id in selected_document_ids
        if document_id in document_map
    ]
    if multi_document_intent and len(selected_documents) < 2:
        selected_documents = _promote_documents(candidate_documents, selected_document_ids, limit=min(4, len(candidate_documents)))
    if not selected_documents:
        if inferred_document_ids:
            selected_documents = [
                document_map[document_id]
                for document_id in inferred_document_ids
                if document_id in document_map
            ]
        if heuristic_clarification:
            add_trace(
                "clarification_gate",
                "Requested clarification after candidate ranking because multiple scopes still match.",
                selected_documents=_summarize_documents(candidate_documents[:4]),
                clarifying_question=heuristic_clarification,
            )
            return SearchAnswer(
                question=question,
                answer=heuristic_clarification,
                document_ids=[],
                retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
                needs_clarification=True,
                clarifying_question=heuristic_clarification,
                trace=trace,
            )
        selected_documents = candidate_documents[: min(3, len(candidate_documents))]
    add_trace(
        "selected_documents",
        "Prepared the final document set for node retrieval.",
        selected_documents=_summarize_documents(selected_documents, limit=6),
    )

    post_selection_clarification = None if multi_document_intent else build_scope_clarification(effective_question, selected_documents)
    if post_selection_clarification:
        add_trace(
            "clarification_gate",
            "Requested clarification because the selected documents still span multiple scopes.",
            selected_documents=_summarize_documents(selected_documents, limit=6),
            clarifying_question=post_selection_clarification,
        )
        return SearchAnswer(
            question=question,
            answer=post_selection_clarification,
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
            needs_clarification=True,
            clarifying_question=post_selection_clarification,
            trace=trace,
        )

    contexts: list[dict] = []
    retrieval_notes: list[str] = [note for note in [rewrite_note, selection_notes] if note]
    for document in selected_documents:
        try:
            node_ids, node_notes = agent.select_nodes(effective_question, document)
            add_trace(
                "node_selection",
                "Selected nodes from the document tree.",
                document_id=document.document_id,
                node_ids=node_ids,
                reasoning=node_notes,
            )
        except Exception:
            node_ids, node_notes = [], None
            add_trace(
                "node_selection",
                "Node selection failed, so heuristic node matching will be used.",
                document_id=document.document_id,
            )
        if not node_ids:
            node_ids = fallback_node_matches(effective_question, document, limit=4)
            add_trace(
                "fallback_nodes",
                "Used heuristic node matching because no node ids were returned.",
                document_id=document.document_id,
                node_ids=node_ids,
            )
        if node_notes:
            retrieval_notes.append(f"{document.document_id}: {node_notes}")
        contexts.extend(build_context_blocks(document, node_ids, max_chars=1600))

    if not contexts:
        raise ValueError("No relevant indexed nodes were found for the question.")
    add_trace(
        "context_building",
        "Built grounded context snippets for answer synthesis.",
        context_count=len(contexts),
        document_ids=[document.document_id for document in selected_documents],
    )

    retrieval_note_text = " | ".join(note for note in retrieval_notes if note) or None
    try:
        answer = agent.answer_from_contexts(
            question,
            contexts[:8],
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=retrieval_note_text,
        )
        add_trace(
            "answer_synthesis",
            "Synthesized the final grounded answer from the selected contexts.",
            answer_preview=answer.answer[:240],
            citation_count=len(answer.citations),
            needs_clarification=answer.needs_clarification,
        )
        answer.trace = trace
        return answer
    except Exception:
        fallback_answer = " ".join(context["text"] for context in contexts[:2] if context.get("text")).strip()
        if not fallback_answer:
            fallback_answer = "I found relevant document nodes, but I could not synthesize a grounded answer."
        add_trace(
            "answer_synthesis",
            "Fell back to raw context because final answer synthesis failed.",
            answer_preview=fallback_answer[:240],
        )
        return SearchAnswer(
            question=question,
            answer=fallback_answer,
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=retrieval_note_text,
            trace=trace,
        )


def answer_question(
    question: str,
    index_dir: str,
    client: LLMPort,
) -> SearchAnswer:
    indexes = load_search_indexes(index_dir)
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

    add_trace(
        "load_indexes",
        "Loaded search indexes.",
        index_dir=index_dir,
        count=len(indexes),
        documents=_summarize_documents(indexes),
    )

    multi_document_intent = question_requests_multi_document_answer(question)
    add_trace(
        "intent_detection",
        "Detected user intent for document scope.",
        multi_document_intent=multi_document_intent,
    )

    initial_candidates = choose_candidate_documents(question, indexes, limit=6)
    add_trace(
        "initial_ranking",
        "Ranked initial candidate documents from the original question.",
        question=question,
        candidates=_summarize_documents(initial_candidates, limit=6),
    )
    ambiguous_candidates = find_ambiguous_candidate_documents(question, initial_candidates)
    if ambiguous_candidates and not question_has_scope_or_detail_hint(question):
        clarification = build_scope_clarification(question, ambiguous_candidates)
        if clarification:
            add_trace(
                "clarification_gate",
                "Stopped early because the question is too generic across multiple document scopes.",
                ambiguous_candidates=_summarize_documents(ambiguous_candidates),
                clarifying_question=clarification,
            )
            return SearchAnswer(
                question=question,
                answer=clarification,
                document_ids=[],
                retrieval_notes="Question is generic and matches multiple document scopes.",
                needs_clarification=True,
                clarifying_question=clarification,
                trace=trace,
            )

    if PageIndexSearchGraphRunner is None:
        return _answer_question_without_langgraph(
            question,
            indexes,
            client,
            multi_document_intent=multi_document_intent,
            trace=trace,
            add_trace=add_trace,
        )

    result = PageIndexSearchGraphRunner(
        client,
        add_trace=add_trace,
        summarize_documents=_summarize_documents,
    ).run(
        question=question,
        indexes=indexes,
        multi_document_intent=multi_document_intent,
    )
    result.trace = trace
    return result
