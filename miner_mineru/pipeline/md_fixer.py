"""
Markdown fixer: normalize heading levels using extracted TOC.

Reads a source markdown file and an LLM-extracted TOC JSON, matches TOC entries to
source lines by title/numbering, and corrects heading levels per the TOC kind mapping:
  - section → # (H1)
  - article → ## (H2)
  - subarticle/subsection → ### (H3)
  - topic → #### (H4)
  - annex → # (H1)

Demotes unmatched # lines before the first TOC match (cover page junk) to plain text.
Preserves all non-heading content unchanged.

Produces corrected markdown + JSON correction report for auditability.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional
from pathlib import Path


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
    match_method: str  # exact, fuzzy, demoted, unmatched


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

def load_toc_from_json(toc_json_path: str) -> List[TOCEntry]:
    """Load TOC entries from step 1 output JSON."""
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
    return toc_entries


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

def match_toc_to_source(toc_entries: List[TOCEntry], source_lines: List[SourceLine]) -> Tuple[Dict[int, TOCEntry], List[str]]:
    """
    Match each TOC entry to a source line using exact + fuzzy matching.
    Returns: (matched_pairs dict {source_line_num: toc_entry}, unmatched_toc_titles)
    """
    matched_pairs = {}
    used_source_indices = set()
    unmatched_toc = []

    for toc_entry in toc_entries:
        # Try exact match first: check if numbering or title appears in any source line
        found = False
        for source_line in source_lines:
            if source_line.line_number - 1 in used_source_indices:
                continue

            search_text = source_line.stripped_text.lower()

            # Exact match: numbering or title is a substring
            if toc_entry.numbering and toc_entry.numbering.lower() in search_text:
                matched_pairs[source_line.line_number] = toc_entry
                used_source_indices.add(source_line.line_number - 1)
                found = True
                break

            if toc_entry.title.lower() in search_text:
                matched_pairs[source_line.line_number] = toc_entry
                used_source_indices.add(source_line.line_number - 1)
                found = True
                break

        if found:
            continue

        # Fuzzy match: SequenceMatcher ratio >= 0.8
        best_ratio = 0.0
        best_line = None
        for source_line in source_lines:
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


def apply_all_corrections(source_lines: List[SourceLine], matched_pairs: Dict[int, TOCEntry]) -> Tuple[List[SourceLine], List[CorrectionEntry]]:
    """Apply all heading level corrections to source lines."""
    corrected_lines = []
    corrections = []

    # Find first TOC match to distinguish cover page from body
    first_match_line = find_first_toc_match_index(source_lines, matched_pairs)

    for source_line in source_lines:
        if source_line.line_number in matched_pairs:
            # Matched TOC entry: re-level based on kind
            toc_entry = matched_pairs[source_line.line_number]
            new_level = kind_to_heading_level(toc_entry.kind)
            corrected_line = apply_heading_level(source_line, new_level)
            corrected_lines.append(corrected_line)

            corrections.append(CorrectionEntry(
                line_number=source_line.line_number,
                old_level=source_line.heading_level,
                new_level=new_level,
                matched_toc_title=toc_entry.title,
                match_method='exact' if toc_entry.numbering and toc_entry.numbering.lower() in source_line.stripped_text.lower() else 'fuzzy',
            ))
        elif source_line.heading_level and first_match_line and source_line.line_number < first_match_line:
            # Unmatched heading BEFORE first TOC match: demote to plain text (cover page junk)
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
            # Everything else: preserve as-is
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

def fix_markdown(source_path: str, toc_json_path: str, output_dir: str) -> CorrectionReport:
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
    toc_entries = load_toc_from_json(toc_json_path)
    source_lines = parse_source_markdown(source_path)

    # Match and correct
    matched_pairs, unmatched_toc = match_toc_to_source(toc_entries, source_lines)
    corrected_lines, corrections = apply_all_corrections(source_lines, matched_pairs)

    # Generate outputs
    source_filename = Path(source_path).name
    corrected_path = os.path.join(output_dir, source_filename)
    report_path = os.path.join(output_dir, Path(source_filename).stem + '_report.json')

    write_corrected_markdown(corrected_lines, corrected_path)

    report = build_correction_report(source_path, corrected_path, source_lines, corrections, unmatched_toc)
    write_correction_report(report, report_path)

    return report
