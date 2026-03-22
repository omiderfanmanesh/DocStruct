"""Pure helpers for ranking and traversing PageIndex document trees."""

from __future__ import annotations

import re
from typing import Any

from docstruct.domain.models import SearchDocumentIndex


_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def tokenize(text: str | None) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _preview(text: str | None, max_chars: int) -> str | None:
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


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
                *metadata_bits,
            ]
        )
        text_tokens = tokenize(haystack)
        overlap = len(question_tokens & text_tokens)
        if document.title:
            overlap += len(question_tokens & tokenize(document.title))
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
                "node_id": str(node.get("node_id") or ""),
                "node_title": str(node.get("title") or ""),
                "line_number": node.get("line_num"),
                "text": _preview(text, max_chars) or "",
            }
        )
    return contexts
