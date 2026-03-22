"""
Markdown fixer: normalize heading levels using TOC-derived heading patterns.

Strategy:
  1. Read TOC entries one by one.
  2. For each entry, use its canonical `pattern` or derive one from
     `numbering + separator + title`.
  3. Search the markdown for that exact heading text.
  4. If found, mark/split the line and re-level it.
  5. If not found and LLM fallback is enabled, ask the LLM to identify noisy
     heading lines for the still-unmatched TOC entries.

The TOC is the source of truth. Exact pattern matching always runs first.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Detect TOC listing lines: lots of dots followed by a page number at line end.
_TOC_LISTING_RE = re.compile(r"(?:\.{3,}|Errore\.)\s*\S*\s*\d*\s*$")

# A small signal set for unresolved heading candidates.
_ARTICLE_SIGNAL_RE = re.compile(
    r"(?:^|\s)(?:art\.|article|section|annex|allegato|articolo|\d+(?:\.\d+)+)\b",
    re.IGNORECASE,
)


def _verbose_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"INFO: {message}", file=sys.stderr)


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class TOCEntry:
    """Extracted heading from the TOC JSON."""

    title: str
    kind: str  # section, article, subarticle, subsection, topic, annex
    depth: int
    numbering: Optional[str] = None
    separator: Optional[str] = None
    pattern: Optional[str] = None
    page: Optional[int] = None
    confidence: float = 1.0

    def build_pattern(self) -> Optional[str]:
        """Build the canonical heading text from TOC fields."""
        if self.numbering and self.separator is not None and self.title:
            return f"{self.numbering}{self.separator}{self.title}"
        if self.numbering and self.title:
            return f"{self.numbering} {self.title}"
        return self.title or None

    def heading_pattern(self) -> Optional[str]:
        return self.pattern or self.build_pattern()

    def search_patterns(self) -> List[str]:
        """Return exact patterns to try, with a few legacy fallbacks."""
        canonical = self.heading_pattern()
        if self.pattern or self.separator is not None or not self.numbering or not self.title:
            return [canonical] if canonical else []

        return [
            f"{self.numbering} - {self.title}",
            f"{self.numbering} – {self.title}",
            f"{self.numbering} -{self.title}",
            f"{self.numbering}: {self.title}",
            f"{self.numbering} {self.title}",
        ]

    def needle(self) -> Optional[str]:
        """Backward-compatible alias for older tests/callers."""
        return self.heading_pattern()


@dataclass
class SourceLine:
    """A line from the source markdown."""

    line_number: int
    raw_text: str
    heading_level: Optional[int] = None
    stripped_text: Optional[str] = None

    def __post_init__(self):
        if self.stripped_text is None:
            self.stripped_text = self.raw_text.lstrip("#").strip()
            if self.raw_text.startswith("#"):
                self.heading_level = len(self.raw_text) - len(self.raw_text.lstrip("#"))


@dataclass
class CorrectionEntry:
    line_number: int
    old_level: Optional[int]
    new_level: Optional[int]
    matched_toc_title: Optional[str]
    match_method: str


@dataclass
class CorrectionReport:
    source_file: str
    output_file: str
    total_lines: int
    lines_changed: int
    lines_demoted: int
    unmatched_toc_entries: List[str] = field(default_factory=list)
    corrections: List[CorrectionEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "source_file": self.source_file,
            "output_file": self.output_file,
            "total_lines": self.total_lines,
            "lines_changed": self.lines_changed,
            "lines_demoted": self.lines_demoted,
            "unmatched_toc_entries": self.unmatched_toc_entries,
            "corrections": [asdict(c) for c in self.corrections],
        }


# ============================================================================
# Loading & Parsing
# ============================================================================


def load_toc_from_json(toc_json_path: str) -> Tuple[List[TOCEntry], Optional[Tuple[int, int]]]:
    """Load TOC entries and optional TOC section boundaries from step 1 output JSON."""
    with open(toc_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    toc_entries: List[TOCEntry] = []
    for entry_dict in data.get("toc", []):
        toc_entries.append(
            TOCEntry(
                title=entry_dict["title"],
                kind=entry_dict["kind"],
                depth=entry_dict["depth"],
                numbering=entry_dict.get("numbering"),
                separator=entry_dict.get("separator"),
                pattern=entry_dict.get("pattern"),
                page=entry_dict.get("page"),
                confidence=entry_dict.get("confidence", 1.0),
            )
        )

    toc_section_range = None
    boundaries = data.get("toc_boundaries", {})
    if boundaries.get("start_line") is not None and boundaries.get("end_line") is not None:
        toc_section_range = (int(boundaries["start_line"]), int(boundaries["end_line"]))

    return toc_entries, toc_section_range


def parse_source_markdown(source_path: str) -> List[SourceLine]:
    """Parse source markdown into SourceLine objects."""
    lines = []
    with open(source_path, "r", encoding="utf-8") as f:
        for line_num, raw_text in enumerate(f, start=1):
            lines.append(SourceLine(line_number=line_num, raw_text=raw_text.rstrip("\n")))
    return lines


# ============================================================================
# Matching Helpers
# ============================================================================


def _line_body_text(source_line: SourceLine) -> str:
    return source_line.stripped_text if source_line.heading_level is not None else source_line.raw_text.strip()


def _is_within_toc_section(
    source_line: SourceLine,
    toc_section_range: Optional[Tuple[int, int]],
) -> bool:
    if not toc_section_range or source_line.line_number <= 0:
        return False
    start_line, end_line = toc_section_range
    return start_line <= source_line.line_number <= end_line


def _should_skip_source_line(
    source_line: SourceLine,
    toc_section_range: Optional[Tuple[int, int]],
) -> bool:
    if _is_within_toc_section(source_line, toc_section_range):
        return True
    return bool(_TOC_LISTING_RE.search(source_line.raw_text))


def _find_substring_ignore_case(haystack: str, needle: str) -> int:
    return haystack.lower().find(needle.lower())


def _build_heading_source_line(
    line_number: int,
    heading_text: str,
    existing_level: Optional[int] = None,
) -> SourceLine:
    level = existing_level or 1
    return SourceLine(line_number=line_number, raw_text=("#" * level) + " " + heading_text.strip())


def _make_synthetic_line_number(parent_line_number: int, fragment_index: int) -> int:
    """
    Generate a stable negative line number for synthetic fragments.

    Using a large multiplier keeps nested splits from bouncing back to a positive
    source line number, which would make plain body text look like a matched
    heading on later passes.
    """

    return -((abs(parent_line_number) * 1_000_000) + fragment_index)


def _split_source_line(
    source_line: SourceLine,
    heading_text: str,
    body_text: Optional[str] = None,
) -> List[SourceLine]:
    """
    Split a line into optional before-text, a heading line, and optional after-text.

    The heading keeps the original line number so corrections are tracked against the
    source document. Synthetic before/after fragments get a negative line number.
    """

    line_text = _line_body_text(source_line)
    idx = _find_substring_ignore_case(line_text, heading_text)

    if idx >= 0:
        before = line_text[:idx].strip()
        after = line_text[idx + len(heading_text) :].strip()
    else:
        before = ""
        after = line_text.strip()

    if body_text is not None and body_text.strip():
        after = body_text.strip()

    result: List[SourceLine] = []
    if before:
        result.append(
            SourceLine(
                line_number=_make_synthetic_line_number(source_line.line_number, 1),
                raw_text=before,
            )
        )
    result.append(
        _build_heading_source_line(
            source_line.line_number,
            heading_text,
            existing_level=source_line.heading_level,
        )
    )
    if after:
        result.append(
            SourceLine(
                line_number=_make_synthetic_line_number(source_line.line_number, 2),
                raw_text=after,
            )
        )
    return result


def _llm_candidate_signals(entry: TOCEntry) -> List[str]:
    signals: List[str] = []
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
    source_lines: List[SourceLine],
    unmatched_entries: List[TOCEntry],
    matched_pairs: Dict[int, TOCEntry],
    toc_section_range: Optional[Tuple[int, int]],
) -> List[Tuple[int, str]]:
    signals = []
    for entry in unmatched_entries:
        signals.extend(_llm_candidate_signals(entry))

    deduped_signals = []
    seen = set()
    for signal in signals:
        key = signal.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_signals.append(signal)

    candidates: List[Tuple[int, str]] = []
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


# ============================================================================
# Exact TOC Matching
# ============================================================================


def apply_heading_level(source_line: SourceLine, new_level: int) -> SourceLine:
    """Return the same heading text with a new markdown heading level."""
    return SourceLine(
        line_number=source_line.line_number,
        raw_text=("#" * new_level) + " " + source_line.stripped_text,
    )


def match_toc_patterns_exactly(
    toc_entries: List[TOCEntry],
    source_lines: List[SourceLine],
    toc_section_range: Optional[Tuple[int, int]] = None,
    verbose: bool = False,
) -> Tuple[List[SourceLine], Dict[int, TOCEntry], List[TOCEntry], Dict[int, str]]:
    """
    Match TOC entries one by one using their exact canonical pattern.

    If the pattern is embedded in a larger line, split that line so the heading can
    be corrected cleanly.
    """

    working_lines = list(source_lines)
    matched_pairs: Dict[int, TOCEntry] = {}
    unmatched_entries: List[TOCEntry] = []
    match_methods: Dict[int, str] = {}

    for entry in toc_entries:
        patterns = entry.search_patterns()
        if not patterns:
            _verbose_log(verbose, f"TOC entry '{entry.title}' has no usable pattern")
            unmatched_entries.append(entry)
            continue

        found = False
        _verbose_log(
            verbose,
            f"Trying exact TOC match for '{entry.title}' with patterns: {patterns}",
        )
        for idx, source_line in enumerate(working_lines):
            if source_line.line_number in matched_pairs:
                continue
            if _should_skip_source_line(source_line, toc_section_range):
                continue

            line_text = _line_body_text(source_line)
            for pattern in patterns:
                match_idx = _find_substring_ignore_case(line_text, pattern)
                if match_idx < 0:
                    continue

                if line_text.strip().lower() == pattern.strip().lower():
                    if source_line.heading_level is None:
                        working_lines[idx] = _build_heading_source_line(source_line.line_number, pattern)
                    matched_pairs[source_line.line_number] = entry
                    match_methods[source_line.line_number] = "exact"
                    _verbose_log(
                        verbose,
                        f"Exact match for '{entry.title}' on line {source_line.line_number}",
                    )
                    found = True
                    break

                working_lines[idx : idx + 1] = _split_source_line(source_line, pattern)
                matched_pairs[source_line.line_number] = entry
                match_methods[source_line.line_number] = "exact"
                _verbose_log(
                    verbose,
                    f"Embedded exact match for '{entry.title}' on line {source_line.line_number}; split line into heading/body",
                )
                found = True
                break

            if found:
                break

        if not found:
            _verbose_log(verbose, f"No exact TOC match found for '{entry.title}'")
            unmatched_entries.append(entry)

    return working_lines, matched_pairs, unmatched_entries, match_methods


def match_toc_to_source(
    toc_entries: List[TOCEntry],
    source_lines: List[SourceLine],
    toc_section_range: Optional[Tuple[int, int]] = None,
) -> Tuple[Dict[int, TOCEntry], List[str]]:
    """
    Backward-compatible wrapper returning only exact TOC matches.

    This keeps the older public helper signature used in tests.
    """

    _, matched_pairs, unmatched_entries, _ = match_toc_patterns_exactly(
        toc_entries,
        source_lines,
        toc_section_range,
    )
    return matched_pairs, [entry.title for entry in unmatched_entries]


# ============================================================================
# LLM Fallback
# ============================================================================


def match_toc_with_llm_fallback(
    toc_entries: List[TOCEntry],
    source_lines: List[SourceLine],
    matched_pairs: Dict[int, TOCEntry],
    toc_section_range: Optional[Tuple[int, int]],
    matcher,
    verbose: bool = False,
) -> Tuple[List[SourceLine], Dict[int, TOCEntry], List[TOCEntry], Dict[int, str]]:
    """
    Ask the LLM to map unresolved TOC entries to noisy source lines.

    The matcher is only used after exact TOC-pattern matching fails.
    """

    if not toc_entries:
        return source_lines, {}, [], {}

    candidate_lines = _collect_llm_candidate_lines(
        source_lines,
        toc_entries,
        matched_pairs,
        toc_section_range,
    )
    _verbose_log(
        verbose,
        f"LLM fallback evaluating {len(toc_entries)} unmatched TOC entries against {len(candidate_lines)} candidate source lines",
    )
    if not candidate_lines:
        _verbose_log(verbose, "LLM fallback skipped because there are no candidate lines")
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

    batch_matches = matcher.batch_match(
        toc_payload,
        candidate_lines,
        set(matched_pairs.keys()),
    )

    working_lines = list(source_lines)
    llm_matches: Dict[int, TOCEntry] = {}
    llm_match_methods: Dict[int, str] = {}
    used_toc_indexes = set()

    for line_number, (toc_index, heading_text, body_text) in sorted(batch_matches.items()):
        if toc_index is None or toc_index < 0 or toc_index >= len(toc_entries):
            continue
        if toc_index in used_toc_indexes:
            continue
        if line_number in matched_pairs or line_number in llm_matches:
            continue

        line_idx = next(
            (idx for idx, source_line in enumerate(working_lines) if source_line.line_number == line_number),
            None,
        )
        if line_idx is None:
            continue

        source_line = working_lines[line_idx]
        heading_to_use = heading_text.strip() or toc_entries[toc_index].heading_pattern()
        if not heading_to_use:
            continue

        working_lines[line_idx : line_idx + 1] = _split_source_line(
            source_line,
            heading_to_use,
            body_text=body_text,
        )
        llm_matches[line_number] = toc_entries[toc_index]
        llm_match_methods[line_number] = "llm"
        used_toc_indexes.add(toc_index)
        _verbose_log(
            verbose,
            f"LLM matched TOC '{toc_entries[toc_index].title}' to line {line_number} as '{heading_to_use}'",
        )

    unresolved_entries = [
        entry for idx, entry in enumerate(toc_entries) if idx not in used_toc_indexes
    ]
    if unresolved_entries:
        _verbose_log(
            verbose,
            "LLM could not resolve: " + ", ".join(entry.title for entry in unresolved_entries),
        )
    return working_lines, llm_matches, unresolved_entries, llm_match_methods


# ============================================================================
# Heading Level Mapping & Correction
# ============================================================================


def kind_to_heading_level(kind: str) -> int:
    mapping = {
        "section": 1,
        "article": 2,
        "subarticle": 3,
        "subsection": 3,
        "topic": 4,
        "annex": 1,
    }
    return mapping.get(kind, 3)


def find_first_toc_match_index(
    source_lines: List[SourceLine],
    matched_pairs: Dict[int, TOCEntry],
) -> Optional[int]:
    if not matched_pairs:
        return None
    matched_line_numbers = [
        source_line.line_number
        for source_line in source_lines
        if source_line.line_number > 0 and source_line.line_number in matched_pairs
    ]
    return min(matched_line_numbers) if matched_line_numbers else None


def apply_all_corrections(
    source_lines: List[SourceLine],
    matched_pairs: Dict[int, TOCEntry],
    toc_entries: List[TOCEntry],
    match_methods: Optional[Dict[int, str]] = None,
) -> Tuple[List[SourceLine], List[CorrectionEntry]]:
    """
    Apply heading level corrections:
      - Matched TOC headings -> correct level based on kind
      - Single heading before first TOC match -> promote to H1 (document title)
      - All other headings -> demote to plain text
    """

    del toc_entries  # kept for API compatibility with existing tests/callers

    corrected_lines = []
    corrections = []
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
            and len(source_line.stripped_text) > 10
        ]
        if len(pre_headings) == 1:
            doc_title_line = pre_headings[0].line_number

    for source_line in source_lines:
        if source_line.line_number in matched_pairs:
            toc_entry = matched_pairs[source_line.line_number]
            new_level = kind_to_heading_level(toc_entry.kind)
            corrected_line = apply_heading_level(source_line, new_level)
            corrected_lines.append(corrected_line)
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
            corrected_line = apply_heading_level(source_line, 1)
            corrected_lines.append(corrected_line)
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
            corrected_lines.append(
                SourceLine(line_number=source_line.line_number, raw_text=source_line.stripped_text)
            )
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


# ============================================================================
# Output
# ============================================================================


def write_corrected_markdown(corrected_lines: List[SourceLine], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for line in corrected_lines:
            f.write(line.raw_text + "\n")


def build_correction_report(
    source_path: str,
    output_path: str,
    source_lines: List[SourceLine],
    corrections: List[CorrectionEntry],
    unmatched_toc: List[str],
) -> CorrectionReport:
    lines_changed = sum(
        1
        for correction in corrections
        if correction.old_level != correction.new_level
        or (correction.old_level and not correction.new_level)
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


def write_correction_report(report: CorrectionReport, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)


# ============================================================================
# Main Entry Point
# ============================================================================


def fix_markdown(
    source_path: str,
    toc_json_path: str,
    output_dir: str,
    use_llm_matching: bool = True,
    verbose: bool = False,
) -> CorrectionReport:
    """
    Fix markdown heading levels using extracted TOC patterns.

    Args:
        source_path: Path to source markdown file
        toc_json_path: Path to step 1 output JSON
        output_dir: Directory to write corrected markdown + report
        use_llm_matching: Enable LLM fallback for unmatched noisy headings
    """

    toc_entries, toc_section_range = load_toc_from_json(toc_json_path)
    source_lines = parse_source_markdown(source_path)
    _verbose_log(verbose, f"Loaded {len(toc_entries)} TOC entries from {toc_json_path}")
    _verbose_log(verbose, f"Parsed {len(source_lines)} source lines from {source_path}")
    if toc_section_range:
        _verbose_log(
            verbose,
            f"TOC section boundaries detected at lines {toc_section_range[0]}-{toc_section_range[1]}",
        )

    source_lines, matched_pairs, unmatched_entries, match_methods = match_toc_patterns_exactly(
        toc_entries,
        source_lines,
        toc_section_range,
        verbose=verbose,
    )
    _verbose_log(
        verbose,
        f"Exact matching finished: {len(matched_pairs)} matched, {len(unmatched_entries)} unmatched",
    )

    if use_llm_matching and unmatched_entries:
        try:
            from docstruct.pipeline.llm_heading_matcher import LLMHeadingMatcher
            from docstruct.providers.factory import build_client

            _verbose_log(verbose, "Starting LLM fallback for unresolved TOC entries")
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
            _verbose_log(
                verbose,
                f"LLM fallback finished: {len(llm_matches)} additional matches, {len(unmatched_entries)} still unmatched",
            )
        except Exception as exc:  # pragma: no cover - defensive fallback path
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
    _verbose_log(verbose, f"Applied {len(corrections)} heading corrections")

    source_filename = Path(source_path).name
    corrected_path = os.path.join(output_dir, source_filename)
    report_path = os.path.join(output_dir, Path(source_filename).stem + "_report.json")

    write_corrected_markdown(corrected_lines, corrected_path)

    report = build_correction_report(
        source_path,
        corrected_path,
        source_lines,
        corrections,
        [entry.title for entry in unmatched_entries],
    )
    write_correction_report(report, report_path)
    _verbose_log(verbose, f"Wrote corrected markdown to {corrected_path}")
    _verbose_log(verbose, f"Wrote correction report to {report_path}")

    return report
