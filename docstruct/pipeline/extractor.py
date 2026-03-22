"""Orchestrates all agents into the full TOC extraction pipeline."""
from __future__ import annotations

import datetime
import sys

from docstruct.agents.boundary_agent import BoundaryAgent
from docstruct.agents.metadata_agent import MetadataAgent
from docstruct.agents.summary_agent import SummaryAgent
from docstruct.models.results import ExtractionResult, LogEntry
from docstruct.pipeline.heading_map import build_heading_map
from docstruct.pipeline.reader import (
    extract_pre_toc_content,
    read_markdown_file,
    slice_toc_content,
)


def extract_toc(file_path: str, client) -> ExtractionResult:
    """Full pipeline: read → detect TOC → classify → summarize → extract metadata."""
    log: list[LogEntry] = []

    lines = read_markdown_file(file_path)
    log.append(LogEntry(action="read", detail=f"Read {len(lines)} lines from {file_path}"))

    boundary, flat_entries = BoundaryAgent(client).run(lines)
    if boundary is None:
        raise ValueError(f"No TOC section found in {file_path}")

    log.append(LogEntry(
        action="detected",
        detail=f"TOC marker '{boundary.marker}' at line {boundary.start_line}",
        line=boundary.start_line,
    ))
    log.append(LogEntry(
        action="boundary",
        detail=f"TOC spans lines {boundary.start_line}–{boundary.end_line}",
    ))

    toc_text = slice_toc_content(lines, boundary)
    pre_toc_text = extract_pre_toc_content(lines, boundary)

    log.append(LogEntry(action="classified", detail=f"LLM extracted {len(flat_entries)} TOC entries"))

    kinds: dict[str, int] = {}
    for e in flat_entries:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    toc_line_count = boundary.end_line - boundary.start_line + 1
    kinds_str = ", ".join(f"{v} {k}" + ("s" if v != 1 else "") for k, v in kinds.items())
    print(f"  TOC: lines {boundary.start_line}–{boundary.end_line} ({toc_line_count} lines), {len(flat_entries)} entries ({kinds_str}) — extracting metadata...", file=sys.stderr)

    heading_map = build_heading_map(flat_entries)
    log.append(LogEntry(action="mapped", detail=f"Built heading tree with {len(heading_map)} root nodes"))

    summary = SummaryAgent(client).run(pre_toc_text, toc_text)
    log.append(LogEntry(action="summarized", detail="Generated document summary"))

    metadata = MetadataAgent(client).run(pre_toc_text)
    log.append(LogEntry(action="metadata", detail=f"Extracted metadata: title='{metadata.title}', source={metadata.source}"))

    return ExtractionResult(
        toc=flat_entries,
        heading_map=heading_map,
        summary=summary,
        metadata=metadata,
        toc_boundaries=boundary,
        processing_log=log,
        extracted_at=datetime.datetime.utcnow().isoformat() + "Z",
    )
