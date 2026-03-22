"""TOC extraction use case."""

from __future__ import annotations

from datetime import datetime, timezone
import sys

from docstruct.application.agents import BoundaryAgent, MetadataAgent, SummaryAgent
from docstruct.domain.heading_map import build_heading_map
from docstruct.domain.models import ExtractionResult, LogEntry
from docstruct.infrastructure.file_io import (
    extract_pre_toc_content,
    read_markdown_file,
    slice_toc_content,
)


def extract_toc(file_path: str, client) -> ExtractionResult:
    log: list[LogEntry] = []
    lines = read_markdown_file(file_path)
    log.append(LogEntry(action="read", detail=f"Read {len(lines)} lines from {file_path}"))

    boundary, flat_entries = BoundaryAgent(client).run(lines)
    if boundary is None:
        raise ValueError(f"No TOC section found in {file_path}")

    log.append(LogEntry(action="detected", detail=f"TOC marker '{boundary.marker}' at line {boundary.start_line}", line=boundary.start_line))
    log.append(LogEntry(action="boundary", detail=f"TOC spans lines {boundary.start_line}-{boundary.end_line}"))

    toc_text = slice_toc_content(lines, boundary)
    pre_toc_text = extract_pre_toc_content(lines, boundary)
    log.append(LogEntry(action="classified", detail=f"LLM extracted {len(flat_entries)} TOC entries"))

    kinds: dict[str, int] = {}
    for entry in flat_entries:
        kinds[entry.kind] = kinds.get(entry.kind, 0) + 1
    toc_line_count = boundary.end_line - boundary.start_line + 1
    kinds_str = ", ".join(f"{count} {kind}" + ("s" if count != 1 else "") for kind, count in kinds.items())
    print(
        f"  TOC: lines {boundary.start_line}-{boundary.end_line} ({toc_line_count} lines), "
        f"{len(flat_entries)} entries ({kinds_str}) - extracting metadata...",
        file=sys.stderr,
    )

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
        extracted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
