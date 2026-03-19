"""
Markdown fixer: normalize heading levels using extracted TOC.

Reads a source markdown file and an LLM-extracted TOC JSON, matches TOC entries to
source lines by title/numbering, and corrects heading levels per the TOC kind mapping:
  - section → # (H1)
  - article → ## (H2)
  - subarticle/subsection → ### (H3)
  - topic → #### (H4)
  - annex → # (H1)

Strategy:
  1. Matched TOC headings → correct level based on their kind
  2. Unmatched headings BEFORE first TOC match → remove heading marker (cover page junk)
  3. Unmatched headings AFTER first TOC match → remove heading marker (not in TOC = not real headings)

This preserves ONLY the TOC structure in markdown. Any heading not in the TOC is
treated as a label/marker and the heading marker is removed entirely.

Preserves all non-heading content unchanged.
Produces corrected markdown + JSON correction report for auditability.
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional
from pathlib import Path


# Pattern to detect TOC listing lines: end with page number like ". 5", ".. 44",
# " 12", etc.  Matches trailing whitespace/dots followed by digits at end of line.
_TOC_PAGE_NUMBER_RE = re.compile(r'[\.\s]+\d+\s*$')


# ============================================================================
# Data Structures (T004, T005)
# ============================================================================

@dataclass
class TOCEntry:
    """Extracted heading from step 1 output JSON."""
    title: str
    kind: str  # section, article, subarticle, subsection, topic, annex
    depth: int
    numbering: Optional[str] = None
    page: Optional[int] = None
    confidence: float = 1.0


@dataclass
class SourceLine:
    """A line from the source markdown."""
    line_number: int
    raw_text: str
    heading_level: Optional[int] = None  # 1 for #, 2 for ##, None if not heading
    stripped_text: Optional[str] = None  # text without # markers

    def __post_init__(self):
        if self.stripped_text is None:
            self.stripped_text = self.raw_text.lstrip('#').strip()
            if self.raw_text.startswith('#'):
                self.heading_level = len(self.raw_text) - len(self.raw_text.lstrip('#'))


@dataclass
class CorrectionEntry:
    """A record of a single heading level change."""
    line_number: int
    old_level: Optional[int]
    new_level: Optional[int]
    matched_toc_title: Optional[str]
    match_method: str  # exact, fuzzy, demoted, llm_inferred, unmatched


@dataclass
class CorrectionReport:
    """Complete report of all corrections."""
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
# Loading & Parsing Functions (T006, T007)
# ============================================================================

def load_toc_from_json(toc_json_path: str) -> Tuple[List[TOCEntry], Optional[Tuple[int, int]]]:
    """Load TOC entries and optional TOC section boundaries from step 1 output JSON.

    Returns:
        (toc_entries, toc_section_range) where toc_section_range is
        (start_line, end_line) or None if boundaries are not available.
    """
    with open(toc_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    toc_entries = []
    for entry_dict in data.get('toc', []):
        toc_entries.append(TOCEntry(
            title=entry_dict['title'],
            kind=entry_dict['kind'],
            depth=entry_dict['depth'],
            numbering=entry_dict.get('numbering'),
            page=entry_dict.get('page'),
            confidence=entry_dict.get('confidence', 1.0),
        ))

    # Load TOC section boundaries so the matcher can skip the TOC listing
    toc_section_range = None
    boundaries = data.get('toc_boundaries', {})
    if boundaries.get('start_line') is not None and boundaries.get('end_line') is not None:
        toc_section_range = (int(boundaries['start_line']), int(boundaries['end_line']))

    return toc_entries, toc_section_range


def parse_source_markdown(source_path: str) -> List[SourceLine]:
    """Parse source markdown, identify heading vs non-heading lines."""
    lines = []
    with open(source_path, 'r', encoding='utf-8') as f:
        for line_num, raw_text in enumerate(f, start=1):
            line = SourceLine(line_number=line_num, raw_text=raw_text.rstrip('\n'))
            lines.append(line)
    return lines


# ============================================================================
# Matching & Matching Helper Functions (T008, T009)
# ============================================================================

def match_toc_to_source(
    toc_entries: List[TOCEntry],
    source_lines: List[SourceLine],
    toc_section_range: Optional[Tuple[int, int]] = None,
) -> Tuple[Dict[int, TOCEntry], List[str]]:
    """
    Match each TOC entry to a source line in the BODY using exact + fuzzy matching.
    Lines inside the TOC listing section are skipped so that matches land on the
    actual body headings, not on their echo in the table of contents.

    Args:
        toc_entries: Extracted TOC entries from step 1
        source_lines: Parsed source markdown lines
        toc_section_range: (start_line, end_line) of the TOC listing to skip,
                           or None to match against all lines

    Returns: (matched_pairs dict {source_line_num: toc_entry}, unmatched_toc_titles)
    """
    matched_pairs = {}
    used_source_indices = set()
    unmatched_toc = []

    # Only match against heading lines that are NOT part of the TOC listing.
    # A TOC listing line is a heading that ends with a page number (e.g. ". 5", ".. 44").
    # Non-heading lines (paragraphs, tables, etc.) are also excluded.
    def _is_toc_listing_line(sl: SourceLine) -> bool:
        """Return True if this heading line looks like a TOC entry (has trailing page number)."""
        return bool(_TOC_PAGE_NUMBER_RE.search(sl.stripped_text))

    candidate_lines = [
        sl for sl in source_lines
        if sl.heading_level is not None and not _is_toc_listing_line(sl)
    ]

    for toc_entry in toc_entries:
        # Try exact match first
        found = False
        title_lower = toc_entry.title.lower()
        num_lower = toc_entry.numbering.lower() if toc_entry.numbering else None

        for source_line in candidate_lines:
            if source_line.line_number - 1 in used_source_indices:
                continue

            search_text = source_line.stripped_text.lower()

            # PRIORITY 1: If entry has numbering, match by numbering FIRST (strong signal)
            # Numbering is typically unique and reliable, even if title differs.
            if num_lower:
                idx = search_text.find(num_lower)
                if idx != -1:
                    end_pos = idx + len(num_lower)
                    # Numbering must be a whole token (not part of "1.2.1" when looking for "1.2")
                    if end_pos >= len(search_text) or search_text[end_pos] in (' ', '\t'):
                        matched_pairs[source_line.line_number] = toc_entry
                        used_source_indices.add(source_line.line_number - 1)
                        found = True
                        break

            # PRIORITY 2: If no numbering, match by title
            else:
                if title_lower == search_text:
                    matched_pairs[source_line.line_number] = toc_entry
                    used_source_indices.add(source_line.line_number - 1)
                    found = True
                    break

                if title_lower in search_text:
                    matched_pairs[source_line.line_number] = toc_entry
                    used_source_indices.add(source_line.line_number - 1)
                    found = True
                    break

        if found:
            continue

        # Fuzzy match: SequenceMatcher ratio >= 0.8
        best_ratio = 0.0
        best_line = None
        for source_line in candidate_lines:
            if source_line.line_number - 1 in used_source_indices:
                continue

            ratio = SequenceMatcher(None, toc_entry.title.lower(), source_line.stripped_text.lower()).ratio()
            if ratio > best_ratio and ratio >= 0.8:
                best_ratio = ratio
                best_line = source_line

        if best_line:
            matched_pairs[best_line.line_number] = toc_entry
            used_source_indices.add(best_line.line_number - 1)
        else:
            unmatched_toc.append(toc_entry.title)

    return matched_pairs, unmatched_toc


def find_first_toc_match_index(source_lines: List[SourceLine], matched_pairs: Dict[int, TOCEntry]) -> Optional[int]:
    """Find the line number of the first TOC-matched heading."""
    if not matched_pairs:
        return None
    return min(matched_pairs.keys())


# ============================================================================
# Heading Level Mapping & Correction Functions (T014, T015, T016)
# ============================================================================

def kind_to_heading_level(kind: str) -> int:
    """Map TOC entry kind to heading level (1-4)."""
    mapping = {
        'section': 1,
        'article': 2,
        'subarticle': 3,
        'subsection': 3,
        'topic': 4,
        'annex': 1,
    }
    return mapping.get(kind, 3)


def collect_unmatched_headings(
    source_lines: List[SourceLine],
    matched_pairs: Dict[int, TOCEntry],
    first_match_line: Optional[int],
) -> List[str]:
    """
    Collect all unmatched headings AFTER first TOC match for batch LLM inference.

    Args:
        source_lines: All source lines
        matched_pairs: Matched TOC entries {line_number: TOCEntry}
        first_match_line: Line number of first TOC match (or None)

    Returns:
        List of unmatched heading texts to be inferred
    """
    unmatched_headings = []
    for source_line in source_lines:
        # Collect unmatched headings AFTER first TOC match
        if (source_line.heading_level and
            first_match_line and
            source_line.line_number > first_match_line and
            source_line.line_number not in matched_pairs):
            unmatched_headings.append(source_line.stripped_text)
    return unmatched_headings



def apply_heading_level(source_line: SourceLine, new_level: int) -> SourceLine:
    """Replace heading markers to match new level, preserving text."""
    if not source_line.heading_level:
        # Add heading marker
        new_raw = '#' * new_level + ' ' + source_line.stripped_text
    else:
        # Replace existing heading marker
        new_raw = '#' * new_level + ' ' + source_line.stripped_text

    new_line = SourceLine(line_number=source_line.line_number, raw_text=new_raw)
    return new_line


def apply_all_corrections(
    source_lines: List[SourceLine],
    matched_pairs: Dict[int, TOCEntry],
    toc_entries: List[TOCEntry],
) -> Tuple[List[SourceLine], List[CorrectionEntry]]:
    """Apply all heading level corrections to source lines.

    Strategy:
    1. Matched TOC headings → correct level based on kind (##, ###, ####, etc.)
    2. Unmatched headings → demote to plain text

    Args:
        source_lines: Source markdown lines
        matched_pairs: Matched TOC entries {line_number: TOCEntry}
        toc_entries: All TOC entries for context
    """
    corrected_lines = []
    corrections = []

    # Find first TOC match to distinguish cover page from body
    first_match_line = find_first_toc_match_index(source_lines, matched_pairs)

    # Apply corrections
    for source_line in source_lines:
        if source_line.line_number in matched_pairs:
            # MATCHED TO TOC: re-level based on kind
            toc_entry = matched_pairs[source_line.line_number]
            new_level = kind_to_heading_level(toc_entry.kind)
            corrected_line = apply_heading_level(source_line, new_level)
            corrected_lines.append(corrected_line)

            match_method = 'exact'
            if toc_entry.numbering and toc_entry.numbering.lower() in source_line.stripped_text.lower():
                match_method = 'exact'
            else:
                match_method = 'fuzzy'

            corrections.append(CorrectionEntry(
                line_number=source_line.line_number,
                old_level=source_line.heading_level,
                new_level=new_level,
                matched_toc_title=toc_entry.title,
                match_method=match_method,
            ))

        elif source_line.heading_level and first_match_line and source_line.line_number < first_match_line:
            # UNMATCHED BEFORE FIRST TOC MATCH: demote to plain text (cover page junk)
            demoted_line = SourceLine(line_number=source_line.line_number, raw_text=source_line.stripped_text)
            corrected_lines.append(demoted_line)

            corrections.append(CorrectionEntry(
                line_number=source_line.line_number,
                old_level=source_line.heading_level,
                new_level=None,
                matched_toc_title=None,
                match_method='demoted',
            ))

        elif source_line.heading_level and first_match_line and source_line.line_number > first_match_line:
            # UNMATCHED AFTER FIRST TOC MATCH: remove heading marker
            # If it's not in the TOC, it's not a real heading - it's just a label/marker
            demoted_line = SourceLine(line_number=source_line.line_number, raw_text=source_line.stripped_text)
            corrected_lines.append(demoted_line)

            corrections.append(CorrectionEntry(
                line_number=source_line.line_number,
                old_level=source_line.heading_level,
                new_level=None,
                matched_toc_title=None,
                match_method='demoted',
            ))

        else:
            # Non-heading content: preserve as-is
            corrected_lines.append(source_line)

    return corrected_lines, corrections


# ============================================================================
# Output Functions (T021, T027, T028)
# ============================================================================

def write_corrected_markdown(corrected_lines: List[SourceLine], output_path: str) -> None:
    """Write corrected markdown to file."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in corrected_lines:
            f.write(line.raw_text + '\n')


def build_correction_report(
    source_path: str,
    output_path: str,
    source_lines: List[SourceLine],
    corrections: List[CorrectionEntry],
    unmatched_toc: List[str],
) -> CorrectionReport:
    """Build a complete correction report."""
    lines_changed = sum(1 for c in corrections if c.old_level != c.new_level or (c.old_level and not c.new_level))
    lines_demoted = sum(1 for c in corrections if c.match_method == 'demoted')

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
    """Write correction report to JSON file."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2)


# ============================================================================
# Main Entry Point (T029)
# ============================================================================

def fix_markdown(
    source_path: str,
    toc_json_path: str,
    output_dir: str,
) -> CorrectionReport:
    """
    Main entry point: fix markdown heading levels using extracted TOC.

    Args:
        source_path: Path to source markdown file
        toc_json_path: Path to step 1 output JSON (contains toc array)
        output_dir: Directory to write corrected markdown + report

    Returns:
        CorrectionReport with all metadata
    """

    # Load inputs
    toc_entries, toc_section_range = load_toc_from_json(toc_json_path)
    source_lines = parse_source_markdown(source_path)

    # Match TOC entries to body headings (skip the TOC listing section)
    matched_pairs, unmatched_toc = match_toc_to_source(toc_entries, source_lines, toc_section_range)
    corrected_lines, corrections = apply_all_corrections(source_lines, matched_pairs, toc_entries)

    # Generate outputs
    source_filename = Path(source_path).name
    corrected_path = os.path.join(output_dir, source_filename)
    report_path = os.path.join(output_dir, Path(source_filename).stem + '_report.json')

    write_corrected_markdown(corrected_lines, corrected_path)

    report = build_correction_report(source_path, corrected_path, source_lines, corrections, unmatched_toc)
    write_correction_report(report, report_path)

    return report
