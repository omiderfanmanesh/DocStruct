"""PageIndex-backed indexing and document QA workflow."""

from __future__ import annotations

import json
from pathlib import Path

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.application.ports import LLMPort
from docstruct.domain.models import DocumentMetadata, SearchAnswer, SearchDocumentIndex
from docstruct.domain.pageindex_search import (
    build_context_blocks,
    build_document_identity_terms,
    build_document_scope_label,
    build_scope_clarification,
    choose_candidate_documents,
    fallback_node_matches,
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
        title=metadata.title if metadata and metadata.title else tree.get("doc_name", source.stem),
        source_path=str(source),
        summary=summary,
        metadata=metadata,
        doc_description=tree.get("doc_description"),
        structure=list(tree.get("structure", [])),
    )
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


def answer_question(
    question: str,
    index_dir: str,
    client: LLMPort,
) -> SearchAnswer:
    indexes = load_search_indexes(index_dir)
    if not indexes:
        raise ValueError(f"No PageIndex search indexes found in {index_dir}")

    agent = PageIndexSearchAgent(client)
    effective_question = question
    rewrite_note = None
    inferred_document_ids: list[str] = []
    try:
        effective_question, rewrite_note, inferred_document_ids = agent.rewrite_question(question, indexes)
    except Exception:
        effective_question, rewrite_note, inferred_document_ids = question, None, []
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
    heuristic_clarification = build_scope_clarification(effective_question, candidate_documents[:4])

    try:
        selection = agent.select_documents(effective_question, candidate_documents)
    except Exception:
        selection = None

    if selection and selection.needs_clarification:
        clarifying_question = selection.clarifying_question or heuristic_clarification
        return SearchAnswer(
            question=question,
            answer=clarifying_question or "I need the university, region, or issuing organization before I can answer safely.",
            document_ids=[],
            retrieval_notes=" | ".join(note for note in [rewrite_note, selection.thinking] if note) or None,
            needs_clarification=True,
            clarifying_question=clarifying_question,
        )

    selected_document_ids = selection.document_ids if selection else []
    selection_notes = selection.thinking if selection else None

    document_map = {document.document_id: document for document in candidate_documents}
    selected_documents = [
        document_map[document_id]
        for document_id in selected_document_ids
        if document_id in document_map
    ]
    if not selected_documents:
        if inferred_document_ids:
            selected_documents = [
                document_map[document_id]
                for document_id in inferred_document_ids
                if document_id in document_map
            ]
        if heuristic_clarification:
            return SearchAnswer(
                question=question,
                answer=heuristic_clarification,
                document_ids=[],
                retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
                needs_clarification=True,
                clarifying_question=heuristic_clarification,
            )
        if not selected_documents:
            selected_documents = candidate_documents[: min(3, len(candidate_documents))]

    post_selection_clarification = build_scope_clarification(effective_question, selected_documents)
    if post_selection_clarification:
        return SearchAnswer(
            question=question,
            answer=post_selection_clarification,
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=" | ".join(note for note in [rewrite_note, selection_notes] if note) or None,
            needs_clarification=True,
            clarifying_question=post_selection_clarification,
        )

    contexts: list[dict] = []
    retrieval_notes: list[str] = [note for note in [rewrite_note, selection_notes] if note]
    for document in selected_documents:
        try:
            node_ids, node_notes = agent.select_nodes(effective_question, document)
        except Exception:
            node_ids, node_notes = [], None
        if not node_ids:
            node_ids = fallback_node_matches(effective_question, document, limit=4)
        if node_notes:
            retrieval_notes.append(f"{document.document_id}: {node_notes}")
        contexts.extend(build_context_blocks(document, node_ids, max_chars=1600))

    if not contexts:
        raise ValueError("No relevant indexed nodes were found for the question.")

    retrieval_note_text = " | ".join(note for note in retrieval_notes if note) or None
    try:
        return agent.answer_from_contexts(
            question,
            contexts[:8],
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=retrieval_note_text,
        )
    except Exception:
        if post_selection_clarification:
            return SearchAnswer(
                question=question,
                answer=post_selection_clarification,
                document_ids=[document.document_id for document in selected_documents],
                retrieval_notes=retrieval_note_text,
                needs_clarification=True,
                clarifying_question=post_selection_clarification,
            )
        fallback_answer = " ".join(context["text"] for context in contexts[:2] if context.get("text")).strip()
        if not fallback_answer:
            fallback_answer = "I found relevant document nodes, but I could not synthesize a grounded answer."
        return SearchAnswer(
            question=question,
            answer=fallback_answer,
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=retrieval_note_text,
        )
