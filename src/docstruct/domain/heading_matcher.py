"""Exact TOC-to-source matching logic without I/O or LLM calls."""

from __future__ import annotations

import re

from docstruct.domain.models import SourceLine, TOCEntry


_TOC_LISTING_RE = re.compile(r"\.{3,}|Errore\.")
_ARTICLE_SIGNAL_RE = re.compile(
    r"(?:^|\s)(?:art\.|article|section|annex|allegato|articolo|\d+(?:\.\d+)+)\b",
    re.IGNORECASE,
)


def _line_body_text(source_line: SourceLine) -> str:
    return source_line.stripped_text if source_line.heading_level is not None else source_line.raw_text.strip()


def _is_within_toc_section(source_line: SourceLine, toc_section_range: tuple[int, int] | None) -> bool:
    if not toc_section_range or source_line.line_number <= 0:
        return False
    start_line, end_line = toc_section_range
    return start_line <= source_line.line_number <= end_line


def _should_skip_source_line(source_line: SourceLine, toc_section_range: tuple[int, int] | None) -> bool:
    del toc_section_range
    return bool(_TOC_LISTING_RE.search(source_line.raw_text))


def _find_substring_ignore_case(haystack: str, needle: str) -> int:
    return haystack.lower().find(needle.lower())


def _build_heading_source_line(
    line_number: int,
    heading_text: str,
    existing_level: int | None = None,
) -> SourceLine:
    level = existing_level or 1
    return SourceLine(line_number=line_number, raw_text=("#" * level) + " " + heading_text.strip())


def _make_synthetic_line_number(parent_line_number: int, fragment_index: int) -> int:
    return -((abs(parent_line_number) * 1_000_000) + fragment_index)


def _split_source_line(
    source_line: SourceLine,
    heading_text: str,
    body_text: str | None = None,
) -> list[SourceLine]:
    line_text = _line_body_text(source_line)
    index = _find_substring_ignore_case(line_text, heading_text)
    if index >= 0:
        before = line_text[:index].strip()
        after = line_text[index + len(heading_text) :].strip()
    else:
        before = ""
        after = line_text.strip()

    if body_text is not None and body_text.strip():
        after = body_text.strip()

    parts: list[SourceLine] = []
    if before:
        parts.append(SourceLine(line_number=_make_synthetic_line_number(source_line.line_number, 1), raw_text=before))
    parts.append(_build_heading_source_line(source_line.line_number, heading_text, existing_level=source_line.heading_level))
    if after:
        parts.append(SourceLine(line_number=_make_synthetic_line_number(source_line.line_number, 2), raw_text=after))
    return parts


def _llm_candidate_signals(entry: TOCEntry) -> list[str]:
    signals: list[str] = []
    pattern = entry.heading_pattern()
    if entry.numbering:
        signals.append(entry.numbering)
    if pattern:
        signals.append(pattern)
    if entry.title:
        title_words = entry.title.split()
        if title_words:
            signals.append(" ".join(title_words[: min(3, len(title_words))]))
    return [signal.strip() for signal in signals if signal and signal.strip()]


def _collect_llm_candidate_lines(
    source_lines: list[SourceLine],
    unmatched_entries: list[TOCEntry],
    matched_pairs: dict[int, TOCEntry],
    toc_section_range: tuple[int, int] | None,
) -> list[tuple[int, str]]:
    deduped_signals: list[str] = []
    seen: set[str] = set()
    for entry in unmatched_entries:
        for signal in _llm_candidate_signals(entry):
            key = signal.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_signals.append(signal)

    candidates: list[tuple[int, str]] = []
    for source_line in source_lines:
        if source_line.line_number <= 0 or source_line.line_number in matched_pairs:
            continue
        if _should_skip_source_line(source_line, toc_section_range):
            continue
        line_text = _line_body_text(source_line)
        if not line_text:
            continue
        if source_line.heading_level is not None:
            candidates.append((source_line.line_number, line_text))
            continue
        if any(_find_substring_ignore_case(line_text, signal) >= 0 for signal in deduped_signals):
            candidates.append((source_line.line_number, line_text))
            continue
        if _ARTICLE_SIGNAL_RE.search(line_text):
            candidates.append((source_line.line_number, line_text))
    return candidates


def match_toc_patterns_exactly(
    toc_entries: list[TOCEntry],
    source_lines: list[SourceLine],
    toc_section_range: tuple[int, int] | None = None,
    verbose: bool = False,
) -> tuple[list[SourceLine], dict[int, TOCEntry], list[TOCEntry], dict[int, str]]:
    del verbose
    working_lines = list(source_lines)
    matched_pairs: dict[int, TOCEntry] = {}
    unmatched_entries: list[TOCEntry] = []
    match_methods: dict[int, str] = {}

    for entry in toc_entries:
        patterns = entry.search_patterns()
        if not patterns:
            unmatched_entries.append(entry)
            continue

        found = False
        for index, source_line in enumerate(working_lines):
            if source_line.line_number in matched_pairs:
                continue
            if _should_skip_source_line(source_line, toc_section_range):
                continue

            line_text = _line_body_text(source_line)
            for pattern in patterns:
                match_index = _find_substring_ignore_case(line_text, pattern)
                if match_index < 0:
                    continue
                if line_text.strip().lower() == pattern.strip().lower():
                    if source_line.heading_level is None:
                        working_lines[index] = _build_heading_source_line(source_line.line_number, pattern)
                    matched_pairs[source_line.line_number] = entry
                    match_methods[source_line.line_number] = "exact"
                    found = True
                    break

                working_lines[index : index + 1] = _split_source_line(source_line, pattern)
                matched_pairs[source_line.line_number] = entry
                match_methods[source_line.line_number] = "exact"
                found = True
                break

            if found:
                break

        if not found:
            unmatched_entries.append(entry)

    return working_lines, matched_pairs, unmatched_entries, match_methods


def match_toc_to_source(
    toc_entries: list[TOCEntry],
    source_lines: list[SourceLine],
    toc_section_range: tuple[int, int] | None = None,
) -> tuple[dict[int, TOCEntry], list[str]]:
    _, matched_pairs, unmatched_entries, _ = match_toc_patterns_exactly(toc_entries, source_lines, toc_section_range)
    return matched_pairs, [entry.title for entry in unmatched_entries]


def match_toc_with_llm_fallback(
    toc_entries: list[TOCEntry],
    source_lines: list[SourceLine],
    matched_pairs: dict[int, TOCEntry],
    toc_section_range: tuple[int, int] | None,
    matcher,
    verbose: bool = False,
) -> tuple[list[SourceLine], dict[int, TOCEntry], list[TOCEntry], dict[int, str]]:
    del verbose
    if not toc_entries:
        return source_lines, {}, [], {}

    candidate_lines = _collect_llm_candidate_lines(source_lines, toc_entries, matched_pairs, toc_section_range)
    if not candidate_lines:
        return source_lines, {}, list(toc_entries), {}

    toc_payload = [
        {
            "title": entry.title,
            "numbering": entry.numbering,
            "kind": entry.kind,
            "pattern": entry.heading_pattern(),
        }
        for entry in toc_entries
    ]
    batch_matches = matcher.batch_match(toc_payload, candidate_lines, set(matched_pairs.keys()))

    working_lines = list(source_lines)
    llm_matches: dict[int, TOCEntry] = {}
    llm_match_methods: dict[int, str] = {}
    used_toc_indexes: set[int] = set()

    for line_number, (toc_index, heading_text, body_text) in sorted(batch_matches.items()):
        if toc_index is None or toc_index < 0 or toc_index >= len(toc_entries):
            continue
        if toc_index in used_toc_indexes or line_number in matched_pairs or line_number in llm_matches:
            continue

        line_index = next((idx for idx, source_line in enumerate(working_lines) if source_line.line_number == line_number), None)
        if line_index is None:
            continue

        source_line = working_lines[line_index]
        heading_to_use = heading_text.strip() or toc_entries[toc_index].heading_pattern()
        if not heading_to_use:
            continue

        working_lines[line_index : line_index + 1] = _split_source_line(source_line, heading_to_use, body_text=body_text)
        llm_matches[line_number] = toc_entries[toc_index]
        llm_match_methods[line_number] = "llm"
        used_toc_indexes.add(toc_index)

    unresolved_entries = [entry for idx, entry in enumerate(toc_entries) if idx not in used_toc_indexes]
    return working_lines, llm_matches, unresolved_entries, llm_match_methods
