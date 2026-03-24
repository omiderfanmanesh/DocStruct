"""Pure helpers for ranking and traversing PageIndex document trees."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docstruct.domain.models import SearchDocumentIndex, SearchProfile


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
_MULTI_DOC_HINTS = (
    "compare",
    "comparison",
    "versus",
    " vs ",
    "across",
    "all files",
    "all documents",
    "all notices",
    "all universities",
    "all regions",
    "each university",
    "each region",
    "every university",
    "every region",
    "list all",
    "show all",
    "across documents",
)
_GENERIC_QUERY_TERMS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "are",
    "the",
    "application",
    "applications",
    "deadline",
    "deadlines",
    "scholarship",
    "scholarships",
    "accommodation",
    "benefits",
    "benefit",
    "call",
    "notice",
    "competition",
    "academic",
    "year",
    "for",
    "students",
    "student",
    "service",
    "services",
}
_SCOPE_SECTION_HINTS = (
    "university",
    "universities",
    "institution",
    "institutions",
    "recipient",
    "recipients",
    "eligible",
    "benefits",
    "students",
    "courses",
    "scope",
    "application",
    "deadlines",
)
_YEAR_RE = re.compile(r"\b(20\d{2}(?:/\d{2,4})?|a\.y\.\s*20\d{2}(?:[./]\d{2,4})?)\b", re.IGNORECASE)
_REGION_PATTERNS = (
    re.compile(r"\b([A-Z][a-z]+)\s+(?:Region|region)\b"),
    re.compile(r"\b([A-Z][a-z]+)\s+(?:Universities|universities)\b"),
)
_ISSUER_PATTERNS = (
    re.compile(r"issued by\s+(.+?)(?:\s+for\b|\s+to\b|,|;|\n)", re.IGNORECASE),
    re.compile(r"\b([A-Z][A-Za-z]*(?:\.[A-Z][A-Za-z]*){2,}\.?)\b"),
    re.compile(r"\b([A-Z]{4,})\b"),
)
_INSTITUTION_PATTERNS = (
    re.compile(r"\bUniversity of [A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5}\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} University\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} Polytechnic(?: University)?\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} Conservatory(?: of [A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,3})?\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} Academy(?: of [A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,3})?\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} School(?: of [A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,3})?\b"),
    re.compile(r"\b[A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,5} Institute(?: of [A-Z][A-Za-z'’&.\-]*(?: [A-Z][A-Za-z'’&.\-]*){0,3})?\b"),
)
_BENEFIT_KEYWORDS = (
    ("scholarship", "scholarship"),
    ("accommodation", "accommodation"),
    ("mobility", "mobility"),
    ("rental contribution", "rental contribution"),
    ("degree award", "degree award"),
    ("canteen", "canteen"),
    ("housing", "accommodation"),
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


def _normalize_titleish(value: str) -> str:
    cleaned = " ".join(value.replace("\u2019", "'").split()).strip(" ,;:.|-")
    return cleaned


def _looks_unknown(value: str | None) -> bool:
    return (value or "").strip().lower() in {"", "unknown", "none", "null", "n/a"}


def _scope_seed_texts(
    document: SearchDocumentIndex,
    *,
    max_nodes: int = 10,
    text_preview_chars: int = 1200,
) -> list[str]:
    texts: list[str] = []
    for value in [
        document.title,
        document.doc_description or "",
        document.metadata.title if document.metadata and document.metadata.title else "",
        document.metadata.organization if document.metadata and document.metadata.organization else "",
        document.summary or "",
    ]:
        normalized = _normalize_titleish(value)
        if normalized and not _looks_unknown(normalized):
            texts.append(normalized)

    flattened = flatten_pageindex_nodes(
        document.structure,
        document_id=document.document_id,
        document_title=document.title,
    )
    scoped_nodes: list[dict[str, Any]] = []
    for node in flattened:
        title = str(node.get("node_title") or "")
        text = str(node.get("text") or "")
        haystack = f"{title}\n{text}".lower()
        if any(hint in haystack for hint in _SCOPE_SECTION_HINTS):
            scoped_nodes.append(node)
    if not scoped_nodes:
        scoped_nodes = flattened[:max_nodes]

    for node in scoped_nodes[:max_nodes]:
        title = _normalize_titleish(str(node.get("node_title") or ""))
        raw_text = str(node.get("text") or "")
        text_preview = _preview(raw_text, text_preview_chars)
        if title:
            texts.append(title)
        if text_preview:
            texts.append(text_preview)
    return _dedupe_preserve_order(texts)


def _extract_matches(patterns: tuple[re.Pattern[str], ...], texts: list[str], *, limit: int = 5) -> list[str]:
    values: list[str] = []
    for text in texts:
        for pattern in patterns:
            for match in pattern.findall(text):
                value = match[0] if isinstance(match, tuple) else match
                normalized = _normalize_titleish(str(value))
                if normalized:
                    values.append(normalized)
    return _dedupe_preserve_order(values)[:limit]


def _extract_cities_from_institutions(institutions: list[str]) -> list[str]:
    cities: list[str] = []
    for institution in institutions:
        match = re.search(r"\bUniversity of ([A-Z][A-Za-z'’.\-]+(?: [A-Z][A-Za-z'’.\-]+){0,2})\b", institution)
        if match:
            cities.append(_normalize_titleish(match.group(1)))
        match = re.search(r"\b([A-Z][A-Za-z'’.\-]+(?: [A-Z][A-Za-z'’.\-]+){0,2}) Polytechnic(?: University)?\b", institution)
        if match:
            cities.append(_normalize_titleish(match.group(1)))
    return _dedupe_preserve_order(cities)[:4]


def _is_informative_issuer(value: str | None) -> bool:
    normalized = _normalize_titleish(value or "")
    if not normalized:
        return False
    lowered = normalized.lower()
    generic_singletons = {
        "section",
        "article",
        "art",
        "universities",
        "university",
        "students",
        "courses",
        "benefits",
        "deadlines",
        "eligible",
    }
    generic_prefixes = (
        "a university",
        "an university",
        "a student support",
        "student support authority",
        "the document",
        "this document",
    )
    if lowered.startswith(generic_prefixes):
        return False
    if lowered in generic_singletons:
        return False
    if normalized.isupper() and "." not in normalized:
        return len(normalized) <= 6
    if any(char.isupper() for char in normalized[1:]) and "." in normalized:
        return True
    words = normalized.split()
    capitalized_words = [word for word in words if word[:1].isupper()]
    return len(capitalized_words) >= 2


def build_search_profile(document: SearchDocumentIndex) -> SearchProfile:
    if document.search_profile:
        return document.search_profile

    texts = _scope_seed_texts(document)
    academic_year = None
    if document.metadata and document.metadata.year and not _looks_unknown(document.metadata.year):
        academic_year = document.metadata.year
    else:
        academic_year = next(
            (
                _normalize_titleish(match.group(1))
                for text in texts
                for match in [_YEAR_RE.search(text)]
                if match is not None
            ),
            None,
        )

    issuer = None
    if document.metadata and document.metadata.organization and not _looks_unknown(document.metadata.organization):
        issuer = _normalize_titleish(document.metadata.organization)
    else:
        issuers = [candidate for candidate in _extract_matches(_ISSUER_PATTERNS, texts, limit=4) if _is_informative_issuer(candidate)]
        issuer = issuers[0] if issuers else None

    regions = _extract_matches(_REGION_PATTERNS, texts, limit=2)
    institutions = _extract_matches(_INSTITUTION_PATTERNS, texts, limit=5)
    cities = _extract_cities_from_institutions(institutions)

    benefit_types: list[str] = []
    haystack = " ".join(texts).lower()
    for keyword, label in _BENEFIT_KEYWORDS:
        if keyword in haystack and label not in benefit_types:
            benefit_types.append(label)

    return SearchProfile(
        issuer=issuer,
        region=regions[0] if regions else None,
        covered_institutions=institutions[:5],
        covered_cities=cities[:4],
        academic_year=academic_year,
        benefit_types=benefit_types[:5],
    )


def build_document_scope_clues(
    document: SearchDocumentIndex,
    *,
    max_nodes: int = 6,
    text_preview_chars: int = 180,
) -> list[str]:
    profile = build_search_profile(document)
    clues = list(build_document_identity_terms(document))
    clues.extend(
        [
            profile.issuer or "",
            profile.region or "",
            profile.academic_year or "",
            *profile.covered_institutions,
            *profile.covered_cities,
            *profile.benefit_types,
        ]
    )
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

    profile = build_search_profile(document)
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
            profile.issuer or "",
            profile.region or "",
            profile.academic_year or "",
            *profile.covered_institutions,
            *profile.covered_cities,
            *profile.benefit_types,
        ]
    )
    return _dedupe_preserve_order(candidates)


def build_document_scope_label(document: SearchDocumentIndex) -> str:
    if document.scope_label:
        return document.scope_label

    profile = build_search_profile(document)
    parts: list[str] = []
    if profile.issuer:
        parts.append(profile.issuer)
    elif document.metadata and document.metadata.organization and not _looks_unknown(document.metadata.organization):
        parts.append(document.metadata.organization)
    elif profile.covered_institutions:
        parts.append(profile.covered_institutions[0])
    elif profile.region:
        parts.append(profile.region)
    if document.title:
        parts.append(document.title)
    if profile.academic_year:
        parts.append(profile.academic_year)
    elif document.metadata and document.metadata.year:
        parts.append(document.metadata.year)

    if not parts:
        parts.append(Path(document.source_path).stem)
    return " | ".join(_dedupe_preserve_order(parts))


def build_distinct_scope_terms(document: SearchDocumentIndex) -> list[str]:
    profile = build_search_profile(document)
    return _dedupe_preserve_order(
        [
            profile.issuer or "",
            profile.region or "",
            *profile.covered_institutions,
            *profile.covered_cities,
        ]
    )


def question_requests_cross_document_reasoning(question: str) -> bool:
    lowered = f" {question.lower()} "
    return any(hint in lowered for hint in _COMPARISON_HINTS)


def question_requests_multi_document_answer(question: str) -> bool:
    lowered = f" {question.lower()} "
    return any(hint in lowered for hint in _MULTI_DOC_HINTS)


def question_has_scope_or_detail_hint(question: str) -> bool:
    tokens = tokenize(question)
    informative = {token for token in tokens if token not in _GENERIC_QUERY_TERMS}
    return bool(informative)


def question_mentions_document_scope(question: str, document: SearchDocumentIndex) -> bool:
    lowered = question.lower()
    question_tokens = tokenize(question)

    distinct_terms = build_distinct_scope_terms(document)
    for phrase in distinct_terms:
        normalized = phrase.lower()
        if len(normalized) >= 4 and normalized in lowered:
            return True

    scope_tokens = tokenize(" ".join(distinct_terms))
    overlap = question_tokens & scope_tokens
    return len(overlap) >= 2


def build_scope_options(documents: list[SearchDocumentIndex], *, limit: int = 4) -> list[str]:
    labels = _dedupe_preserve_order([build_user_facing_scope_label(document) for document in documents])
    return labels[:limit]


def build_user_facing_scope_label(document: SearchDocumentIndex) -> str:
    profile = build_search_profile(document)
    parts: list[str] = []

    if profile.region:
        parts.append(profile.region)

    location_hints = profile.covered_cities[:2]
    if location_hints:
        parts.append(" / ".join(location_hints))

    institution_hints = profile.covered_institutions[:2]
    if institution_hints:
        parts.append(", ".join(institution_hints))
    elif profile.issuer:
        parts.append(profile.issuer)
    elif document.metadata and document.metadata.organization and not _looks_unknown(document.metadata.organization):
        parts.append(document.metadata.organization)

    if profile.academic_year:
        parts.append(profile.academic_year)
    elif document.metadata and document.metadata.year and not _looks_unknown(document.metadata.year):
        parts.append(document.metadata.year)

    if parts:
        return " | ".join(_dedupe_preserve_order(parts))
    return build_document_scope_label(document)


def build_scope_clarification(question: str, documents: list[SearchDocumentIndex]) -> str | None:
    if len(documents) < 2 or question_requests_multi_document_answer(question):
        return None
    if any(question_mentions_document_scope(question, document) for document in documents):
        return None

    options = build_scope_options(documents)
    if len(options) < 2:
        return None
    joined = "; ".join(options)
    return (
        "I found matching policy documents for different universities or regions. "
        f"Please specify the university, region, or issuing organization. Options: {joined}."
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
        return score_document_match(question, document, question_tokens=question_tokens)

    ranked = sorted(documents, key=lambda document: (score(document), document.title), reverse=True)
    positive = [document for document in ranked if score(document) > 0]
    if positive:
        minimum = min(limit, max(3, len(positive)))
        return ranked[:minimum]
    return ranked[:limit]


def score_document_match(
    question: str,
    document: SearchDocumentIndex,
    *,
    question_tokens: set[str] | None = None,
) -> int:
    tokens = question_tokens if question_tokens is not None else tokenize(question)
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
    overlap = len(tokens & text_tokens)
    if document.title:
        overlap += len(tokens & tokenize(document.title))
    if question_mentions_document_scope(question, document):
        overlap += 8
    return overlap


def find_ambiguous_candidate_documents(
    question: str,
    documents: list[SearchDocumentIndex],
    *,
    limit: int = 4,
) -> list[SearchDocumentIndex]:
    if len(documents) < 2 or question_requests_multi_document_answer(question):
        return []
    if any(question_mentions_document_scope(question, document) for document in documents):
        return []

    question_tokens = tokenize(question)
    ranked = sorted(
        (
            (score_document_match(question, document, question_tokens=question_tokens), document)
            for document in documents
        ),
        key=lambda item: (item[0], item[1].title),
        reverse=True,
    )
    positive = [(score, document) for score, document in ranked if score > 0]
    if len(positive) < 2:
        return []
    top_score = positive[0][0]
    ambiguous = [
        document
        for score, document in positive
        if score >= max(1, top_score - 2)
    ]
    return ambiguous[:limit] if len(ambiguous) >= 2 else []


def fallback_node_matches(
    question: str,
    document: SearchDocumentIndex,
    *,
    limit: int = 4,
) -> list[str]:
    question_tokens = tokenize(question)
    lowered_question = question.lower()
    nodes = flatten_pageindex_nodes(document.structure, document_id=document.document_id, document_title=document.title)

    def score(node: dict[str, Any]) -> int:
        title = str(node.get("node_title") or "")
        path = str(node.get("path") or "")
        summary = str(node.get("summary") or "")
        text = str(node.get("text") or "")
        haystack = f"{title}\n{path}\n{summary}\n{text}".lower()

        overlap = len(question_tokens & tokenize(title)) * 4
        overlap += len(question_tokens & tokenize(path)) * 3
        overlap += len(question_tokens & tokenize(summary)) * 2
        overlap += min(len(question_tokens & tokenize(text)), 6)

        if "deadline for submitting the application" in haystack:
            overlap += 20
        if "methods and deadlines for submitting the application" in haystack:
            overlap += 14
        if "paid accommodation self-certification" in haystack:
            overlap += 12
        if "scholarship and accommodation service" in haystack and "deadline" in haystack:
            overlap += 10
        if "application" in haystack and "deadline" in haystack:
            overlap += 8
        if "accommodation" in lowered_question and ("accommodation" in haystack or "residence" in haystack):
            overlap += 6

        if "ranking" not in lowered_question:
            if "ranking" in haystack or "rankings" in haystack:
                overlap -= 8
            if "complaint" in haystack or "complaints" in haystack:
                overlap -= 6
            if "provisional" in haystack or "definitive" in haystack:
                overlap -= 4

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
    question: str | None = None,
    max_chars: int = 1600,
) -> list[dict[str, Any]]:
    question_tokens = tokenize(question)
    contexts: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def candidate_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = [node]
        children = list(node.get("nodes", []))
        if not children:
            return selected

        descendant_candidates = flatten_pageindex_nodes(
            children,
            document_id=document.document_id,
            document_title=document.title,
        )

        def descendant_score(item: dict[str, Any]) -> int:
            title = str(item.get("node_title") or "")
            path = str(item.get("path") or "")
            summary = str(item.get("summary") or "")
            text = str(item.get("text") or "")
            overlap = len(question_tokens & tokenize(title)) * 5
            overlap += len(question_tokens & tokenize(path)) * 4
            overlap += len(question_tokens & tokenize(summary)) * 3
            overlap += min(len(question_tokens & tokenize(text)), 8)

            focus_haystack = f"{title}\n{path}\n{summary}\n{text}".lower()
            if "deadline" in focus_haystack or "deadlines" in focus_haystack:
                overlap += 8
            if "application" in focus_haystack or "submit" in focus_haystack:
                overlap += 5
            if "accommodation" in focus_haystack or "residence" in focus_haystack or "housing" in focus_haystack:
                overlap += 4
            if "ranking" in focus_haystack or "complaint" in focus_haystack:
                overlap += 2
            return overlap

        ranked_descendants = sorted(
            descendant_candidates,
            key=lambda item: (descendant_score(item), str(item.get("node_title") or "")),
            reverse=True,
        )
        for descendant in ranked_descendants[:2]:
            if descendant_score(descendant) > 0:
                selected.append(descendant)
        return selected

    for node in find_nodes_by_id(document.structure, node_ids):
        for candidate in candidate_nodes(node):
            candidate_node_id = str(candidate.get("node_id") or "")
            if not candidate_node_id or candidate_node_id in seen_node_ids:
                continue
            seen_node_ids.add(candidate_node_id)
            raw_text = candidate.get("text") or candidate.get("summary") or candidate.get("prefix_summary") or ""
            node_title = str(candidate.get("title") or candidate.get("node_title") or "")
            line_number = candidate.get("line_num") if candidate.get("line_num") is not None else candidate.get("line_number")
            search_profile = build_search_profile(document)
            contexts.append(
                {
                    "document_id": document.document_id,
                    "document_title": document.title,
                    "scope_label": build_document_scope_label(document),
                    "organization": document.metadata.organization if document.metadata else None,
                    "year": document.metadata.year if document.metadata else None,
                    "issuer": search_profile.issuer,
                    "region": search_profile.region,
                    "covered_institutions": search_profile.covered_institutions[:4],
                    "node_id": candidate_node_id,
                    "node_title": node_title,
                    "line_number": line_number,
                    "text": _preview(raw_text, max_chars) or "",
                }
            )
    return contexts
