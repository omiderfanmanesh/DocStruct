"""Pure helpers for ranking and traversing PageIndex document trees."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docstruct.domain.models import SearchDocumentIndex


_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_COMPARISON_HINTS = (
    "compare",
    "comparison",
    "versus",
    " vs ",
    "difference",
    "different",
    "across",
    "all universities",
    "all regions",
    "each university",
    "each region",
)


def tokenize(text: str | None) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _preview(text: str | None, max_chars: int) -> str | None:
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def build_document_scope_clues(
    document: SearchDocumentIndex,
    *,
    max_nodes: int = 6,
    text_preview_chars: int = 180,
) -> list[str]:
    clues = list(build_document_identity_terms(document))
    added = 0
    for node in flatten_pageindex_nodes(
        document.structure,
        document_id=document.document_id,
        document_title=document.title,
    ):
        if added >= max_nodes:
            break
        node_title = str(node.get("node_title") or "").strip()
        if node_title:
            clues.append(node_title)
        text_preview = _preview(str(node.get("text") or ""), text_preview_chars)
        if text_preview:
            clues.append(text_preview)
        added += 1
    return _dedupe_preserve_order(clues)


def build_document_identity_terms(document: SearchDocumentIndex) -> list[str]:
    if document.identity_terms:
        return _dedupe_preserve_order(document.identity_terms)

    candidates: list[str] = []
    if document.metadata:
        candidates.extend(
            [
                document.metadata.organization or "",
                document.metadata.title or "",
                document.metadata.year or "",
                document.metadata.document_type or "",
            ]
        )
    candidates.extend(
        [
            document.title,
            Path(document.source_path).stem.replace("_", " ").replace("-", " "),
            document.doc_description or "",
        ]
    )
    return _dedupe_preserve_order(candidates)


def build_document_scope_label(document: SearchDocumentIndex) -> str:
    if document.scope_label:
        return document.scope_label

    parts: list[str] = []
    if document.metadata and document.metadata.organization:
        parts.append(document.metadata.organization)
    if document.title:
        parts.append(document.title)
    if document.metadata and document.metadata.year:
        parts.append(document.metadata.year)

    if not parts:
        parts.append(Path(document.source_path).stem)
    return " | ".join(_dedupe_preserve_order(parts))


def question_requests_cross_document_reasoning(question: str) -> bool:
    lowered = f" {question.lower()} "
    return any(hint in lowered for hint in _COMPARISON_HINTS)


def question_mentions_document_scope(question: str, document: SearchDocumentIndex) -> bool:
    lowered = question.lower()
    question_tokens = tokenize(question)

    for phrase in build_document_identity_terms(document):
        normalized = phrase.lower()
        if len(normalized) >= 4 and normalized in lowered:
            return True

    scope_tokens = tokenize(" ".join(build_document_identity_terms(document)))
    overlap = question_tokens & scope_tokens
    return len(overlap) >= 2


def build_scope_options(documents: list[SearchDocumentIndex], *, limit: int = 4) -> list[str]:
    labels = _dedupe_preserve_order([build_document_scope_label(document) for document in documents])
    return labels[:limit]


def build_scope_clarification(question: str, documents: list[SearchDocumentIndex]) -> str | None:
    if len(documents) < 2 or question_requests_cross_document_reasoning(question):
        return None
    if any(question_mentions_document_scope(question, document) for document in documents):
        return None

    options = build_scope_options(documents)
    if len(options) < 2:
        return None
    joined = "; ".join(options)
    return (
        "I found matching policy documents for different universities or regions. "
        f"Which one should I use: {joined}?"
    )


def flatten_pageindex_nodes(
    structure: list[dict[str, Any]],
    *,
    document_id: str,
    document_title: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def walk(items: list[dict[str, Any]], trail: list[str]) -> None:
        for item in items:
            title = str(item.get("title") or "").strip()
            path = trail + ([title] if title else [])
            nodes.append(
                {
                    "document_id": document_id,
                    "document_title": document_title,
                    "node_id": str(item.get("node_id") or ""),
                    "node_title": title,
                    "path": " > ".join(path),
                    "line_number": item.get("line_num"),
                    "summary": item.get("summary") or item.get("prefix_summary"),
                    "text": item.get("text") or "",
                }
            )
            walk(list(item.get("nodes", [])), path)

    walk(structure, [])
    return nodes


def build_tree_outline(
    structure: list[dict[str, Any]],
    *,
    max_nodes: int = 60,
    preview_chars: int = 180,
) -> list[dict[str, Any]]:
    emitted = 0

    def walk(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal emitted
        outline: list[dict[str, Any]] = []
        for item in items:
            if emitted >= max_nodes:
                break
            emitted += 1
            node = {
                "title": item.get("title"),
                "node_id": item.get("node_id"),
                "line_num": item.get("line_num"),
            }
            summary = _preview(item.get("summary") or item.get("prefix_summary"), preview_chars)
            if summary:
                node["summary"] = summary
            else:
                text_preview = _preview(item.get("text"), preview_chars)
                if text_preview:
                    node["text_preview"] = text_preview
            children = walk(list(item.get("nodes", [])))
            if children:
                node["nodes"] = children
            outline.append(node)
        return outline

    return walk(structure)


def choose_candidate_documents(
    question: str,
    documents: list[SearchDocumentIndex],
    *,
    limit: int = 6,
) -> list[SearchDocumentIndex]:
    question_tokens = tokenize(question)
    if not question_tokens:
        return documents[:limit]

    def score(document: SearchDocumentIndex) -> int:
        metadata_bits = []
        if document.metadata:
            metadata_bits.extend(
                [
                    document.metadata.document_type or "",
                    document.metadata.organization or "",
                    document.metadata.year or "",
                ]
            )
        haystack = " ".join(
            [
                document.title,
                document.summary or "",
                document.doc_description or "",
                build_document_scope_label(document),
                *build_document_scope_clues(document),
                *metadata_bits,
            ]
        )
        text_tokens = tokenize(haystack)
        overlap = len(question_tokens & text_tokens)
        if document.title:
            overlap += len(question_tokens & tokenize(document.title))
        if question_mentions_document_scope(question, document):
            overlap += 8
        return overlap

    ranked = sorted(documents, key=lambda document: (score(document), document.title), reverse=True)
    positive = [document for document in ranked if score(document) > 0]
    if positive:
        minimum = min(limit, max(3, len(positive)))
        return ranked[:minimum]
    return ranked[:limit]


def fallback_node_matches(
    question: str,
    document: SearchDocumentIndex,
    *,
    limit: int = 4,
) -> list[str]:
    question_tokens = tokenize(question)
    nodes = flatten_pageindex_nodes(document.structure, document_id=document.document_id, document_title=document.title)

    def score(node: dict[str, Any]) -> int:
        overlap = len(question_tokens & tokenize(node.get("node_title")))
        overlap += len(question_tokens & tokenize(node.get("path"))) * 2
        overlap += len(question_tokens & tokenize(node.get("summary")))
        overlap += min(len(question_tokens & tokenize(node.get("text"))), 3)
        return overlap

    ranked = sorted(nodes, key=lambda node: (score(node), str(node.get("node_title"))), reverse=True)
    positive = [node for node in ranked if score(node) > 0]
    selected = positive[:limit] if positive else ranked[:limit]
    return [str(node.get("node_id")) for node in selected if node.get("node_id")]


def find_nodes_by_id(
    structure: list[dict[str, Any]],
    node_ids: list[str],
) -> list[dict[str, Any]]:
    wanted = {str(node_id) for node_id in node_ids}
    found: dict[str, dict[str, Any]] = {}

    def walk(items: list[dict[str, Any]]) -> None:
        for item in items:
            node_id = str(item.get("node_id") or "")
            if node_id in wanted:
                found[node_id] = item
            walk(list(item.get("nodes", [])))

    walk(structure)
    return [found[node_id] for node_id in node_ids if node_id in found]


def build_context_blocks(
    document: SearchDocumentIndex,
    node_ids: list[str],
    *,
    max_chars: int = 1600,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for node in find_nodes_by_id(document.structure, node_ids):
        text = node.get("text") or node.get("summary") or node.get("prefix_summary") or ""
        contexts.append(
            {
                "document_id": document.document_id,
                "document_title": document.title,
                "scope_label": build_document_scope_label(document),
                "organization": document.metadata.organization if document.metadata else None,
                "year": document.metadata.year if document.metadata else None,
                "node_id": str(node.get("node_id") or ""),
                "node_title": str(node.get("title") or ""),
                "line_number": node.get("line_num"),
                "text": _preview(text, max_chars) or "",
            }
        )
    return contexts
