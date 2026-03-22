"""PageIndex-backed indexing and document QA workflow."""

from __future__ import annotations

import json
from pathlib import Path

from docstruct.application.agents.pageindex_search_agent import PageIndexSearchAgent
from docstruct.application.ports import LLMPort
from docstruct.domain.models import DocumentMetadata, SearchAnswer, SearchDocumentIndex
from docstruct.domain.pageindex_search import (
    build_context_blocks,
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


def answer_question(
    question: str,
    index_dir: str,
    client: LLMPort,
) -> SearchAnswer:
    indexes = load_search_indexes(index_dir)
    if not indexes:
        raise ValueError(f"No PageIndex search indexes found in {index_dir}")

    candidate_documents = choose_candidate_documents(question, indexes, limit=6)
    agent = PageIndexSearchAgent(client)

    try:
        selected_document_ids, selection_notes = agent.select_documents(question, candidate_documents)
    except Exception:
        selected_document_ids, selection_notes = [], None

    document_map = {document.document_id: document for document in candidate_documents}
    selected_documents = [
        document_map[document_id]
        for document_id in selected_document_ids
        if document_id in document_map
    ]
    if not selected_documents:
        selected_documents = candidate_documents[: min(3, len(candidate_documents))]

    contexts: list[dict] = []
    retrieval_notes: list[str] = [selection_notes] if selection_notes else []
    for document in selected_documents:
        try:
            node_ids, node_notes = agent.select_nodes(question, document)
        except Exception:
            node_ids, node_notes = [], None
        if not node_ids:
            node_ids = fallback_node_matches(question, document, limit=4)
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
        fallback_answer = " ".join(context["text"] for context in contexts[:2] if context.get("text")).strip()
        if not fallback_answer:
            fallback_answer = "I found relevant document nodes, but I could not synthesize a grounded answer."
        return SearchAnswer(
            question=question,
            answer=fallback_answer,
            document_ids=[document.document_id for document in selected_documents],
            retrieval_notes=retrieval_note_text,
        )
