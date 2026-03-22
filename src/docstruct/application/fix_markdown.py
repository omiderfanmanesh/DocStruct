"""Markdown fixing use case."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from docstruct.application.agents.llm_heading_matcher import LLMHeadingMatcher
from docstruct.domain.heading_matcher import (
    match_toc_patterns_exactly,
    match_toc_to_source,
    match_toc_with_llm_fallback,
)
from docstruct.domain.level_mapper import (
    apply_all_corrections,
    apply_heading_level,
    find_first_toc_match_index,
    kind_to_heading_level,
)
from docstruct.domain.models import CorrectionReport, SourceLine, TOCEntry
from docstruct.infrastructure.file_io import (
    parse_source_markdown,
    write_correction_report,
    write_corrected_markdown,
)
from docstruct.infrastructure.llm.factory import build_client


def _verbose_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"INFO: {message}", file=sys.stderr)


def load_toc_from_json(toc_json_path: str) -> tuple[list[TOCEntry], tuple[int, int] | None]:
    with open(toc_json_path, encoding="utf-8") as handle:
        data = json.load(handle)

    toc_entries = [
        TOCEntry(
            title=entry["title"],
            kind=entry["kind"],
            depth=entry["depth"],
            numbering=entry.get("numbering"),
            separator=entry.get("separator"),
            pattern=entry.get("pattern"),
            page=entry.get("page"),
            confidence=entry.get("confidence", 1.0),
        )
        for entry in data.get("toc", [])
    ]

    toc_section_range = None
    boundaries = data.get("toc_boundaries", {})
    if boundaries.get("start_line") is not None and boundaries.get("end_line") is not None:
        toc_section_range = (int(boundaries["start_line"]), int(boundaries["end_line"]))
    return toc_entries, toc_section_range


def build_correction_report(
    source_path: str,
    output_path: str,
    source_lines: list[SourceLine],
    corrections,
    unmatched_toc: list[str],
) -> CorrectionReport:
    lines_changed = sum(
        1
        for correction in corrections
        if correction.old_level != correction.new_level or (correction.old_level and not correction.new_level)
    )
    lines_demoted = sum(1 for correction in corrections if correction.match_method == "demoted")
    return CorrectionReport(
        source_file=source_path,
        output_file=output_path,
        total_lines=len(source_lines),
        lines_changed=lines_changed,
        lines_demoted=lines_demoted,
        unmatched_toc_entries=unmatched_toc,
        corrections=corrections,
    )


def fix_markdown(
    source_path: str,
    toc_json_path: str,
    output_dir: str,
    use_llm_matching: bool = True,
    verbose: bool = False,
) -> CorrectionReport:
    toc_entries, toc_section_range = load_toc_from_json(toc_json_path)
    source_lines = parse_source_markdown(source_path)
    _verbose_log(verbose, f"Loaded {len(toc_entries)} TOC entries from {toc_json_path}")
    _verbose_log(verbose, f"Parsed {len(source_lines)} source lines from {source_path}")

    source_lines, matched_pairs, unmatched_entries, match_methods = match_toc_patterns_exactly(
        toc_entries,
        source_lines,
        toc_section_range,
        verbose=verbose,
    )
    _verbose_log(verbose, f"Exact matching finished: {len(matched_pairs)} matched, {len(unmatched_entries)} unmatched")

    if use_llm_matching and unmatched_entries:
        try:
            matcher = LLMHeadingMatcher(build_client())
            source_lines, llm_matches, unmatched_entries, llm_methods = match_toc_with_llm_fallback(
                unmatched_entries,
                source_lines,
                matched_pairs,
                toc_section_range,
                matcher,
                verbose=verbose,
            )
            matched_pairs.update(llm_matches)
            match_methods.update(llm_methods)
            _verbose_log(verbose, f"LLM fallback finished: {len(llm_matches)} additional matches, {len(unmatched_entries)} still unmatched")
        except Exception as exc:  # pragma: no cover
            print(f"WARNING: LLM fallback skipped: {exc}", file=sys.stderr)
    elif not unmatched_entries:
        _verbose_log(verbose, "All TOC entries matched exactly; LLM fallback not needed")
    else:
        _verbose_log(verbose, "LLM fallback disabled; leaving unmatched TOC entries in the report")

    corrected_lines, corrections = apply_all_corrections(
        source_lines,
        matched_pairs,
        toc_entries,
        match_methods=match_methods,
    )

    source_filename = Path(source_path).name
    corrected_path = str(Path(output_dir) / source_filename)
    report_path = str(Path(output_dir) / f"{Path(source_filename).stem}_report.json")

    write_corrected_markdown(corrected_lines, corrected_path)
    report = build_correction_report(
        source_path,
        corrected_path,
        source_lines,
        corrections,
        [entry.title for entry in unmatched_entries],
    )
    write_correction_report(report, report_path)
    return report


__all__ = [
    "apply_all_corrections",
    "apply_heading_level",
    "build_correction_report",
    "find_first_toc_match_index",
    "fix_markdown",
    "kind_to_heading_level",
    "load_toc_from_json",
    "match_toc_to_source",
]

