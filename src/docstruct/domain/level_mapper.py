"""Heading level mapping and correction logic."""

from __future__ import annotations

from docstruct.domain.models import CorrectionEntry, SourceLine, TOCEntry


def kind_to_heading_level(kind: str) -> int:
    return {
        "section": 1,
        "article": 2,
        "subarticle": 3,
        "subsection": 3,
        "topic": 4,
        "annex": 1,
    }.get(kind, 3)


def apply_heading_level(source_line: SourceLine, new_level: int) -> SourceLine:
    return SourceLine(
        line_number=source_line.line_number,
        raw_text=("#" * new_level) + " " + (source_line.stripped_text or ""),
    )


def find_first_toc_match_index(
    source_lines: list[SourceLine],
    matched_pairs: dict[int, TOCEntry],
) -> int | None:
    if not matched_pairs:
        return None
    matched_line_numbers = [
        source_line.line_number
        for source_line in source_lines
        if source_line.line_number > 0 and source_line.line_number in matched_pairs
    ]
    return min(matched_line_numbers) if matched_line_numbers else None


def apply_all_corrections(
    source_lines: list[SourceLine],
    matched_pairs: dict[int, TOCEntry],
    toc_entries: list[TOCEntry],
    match_methods: dict[int, str] | None = None,
) -> tuple[list[SourceLine], list[CorrectionEntry]]:
    del toc_entries
    corrected_lines: list[SourceLine] = []
    corrections: list[CorrectionEntry] = []
    match_methods = match_methods or {}
    first_match_line = find_first_toc_match_index(source_lines, matched_pairs)

    doc_title_line = None
    if first_match_line:
        pre_headings = [
            source_line
            for source_line in source_lines
            if source_line.heading_level is not None
            and source_line.line_number > 0
            and source_line.line_number < first_match_line
            and source_line.line_number not in matched_pairs
            and len(source_line.stripped_text or "") > 10
        ]
        if len(pre_headings) == 1:
            doc_title_line = pre_headings[0].line_number

    for source_line in source_lines:
        if source_line.line_number in matched_pairs:
            toc_entry = matched_pairs[source_line.line_number]
            new_level = kind_to_heading_level(toc_entry.kind)
            corrected_lines.append(apply_heading_level(source_line, new_level))
            corrections.append(
                CorrectionEntry(
                    line_number=source_line.line_number,
                    old_level=source_line.heading_level,
                    new_level=new_level,
                    matched_toc_title=toc_entry.title,
                    match_method=match_methods.get(source_line.line_number, "exact"),
                )
            )
        elif source_line.line_number == doc_title_line:
            corrected_lines.append(apply_heading_level(source_line, 1))
            corrections.append(
                CorrectionEntry(
                    line_number=source_line.line_number,
                    old_level=source_line.heading_level,
                    new_level=1,
                    matched_toc_title=None,
                    match_method="doc_title",
                )
            )
        elif source_line.heading_level is not None and first_match_line:
            corrected_lines.append(SourceLine(line_number=source_line.line_number, raw_text=source_line.stripped_text or ""))
            corrections.append(
                CorrectionEntry(
                    line_number=source_line.line_number,
                    old_level=source_line.heading_level,
                    new_level=None,
                    matched_toc_title=None,
                    match_method="demoted",
                )
            )
        else:
            corrected_lines.append(source_line)

    return corrected_lines, corrections
