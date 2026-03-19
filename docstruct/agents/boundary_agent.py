"""BoundaryAgent — finds TOC start/end via LLM sliding-window over document lines."""
from __future__ import annotations

import json
import re
import sys

from docstruct.models.document import TOCBoundary

_CHUNK_SIZE = 100


class BoundaryAgent:
    """Scans document lines in 100-line chunks to locate the TOC section."""

    def __init__(self, client):
        self._client = client

    def run(self, lines: list[str]) -> TOCBoundary | None:
        """Return TOCBoundary or None if no TOC found."""
        MAX_LINES = 600
        scan_lines = lines[:MAX_LINES]

        toc_start_abs = None
        toc_end_abs = None
        status = "searching"

        chunk_start = 0
        while chunk_start < len(scan_lines):
            chunk = scan_lines[chunk_start : chunk_start + _CHUNK_SIZE]
            numbered = "".join(
                f"[{chunk_start + i}] {line}" for i, line in enumerate(chunk)
            )

            prompt = (
                "You are scanning a MinerU-extracted markdown document to find the Table of Contents (TOC).\n\n"
                "The TOC may be labeled with a heading like '# Summary', '# TABLE OF CONTENTS', "
                "'# Sommario', '# Indice', or have no heading at all (entries start directly).\n"
                "TOC entries look like: article/section titles with optional page numbers, "
                "decimal numbering (1.1, 2.3), or 'Art. N / Article N' prefixes.\n"
                "Body prose looks like: full sentences, definitions, legal clauses — NOT title listings.\n\n"
                f"Current scan status: {status}\n\n"
                "Below are document lines with their absolute line numbers in [brackets].\n"
                "Analyze this chunk and return a JSON object with:\n"
                '  "toc_start": absolute line number where TOC begins in this chunk, or -1 if TOC has not started yet\n'
                '  "toc_end": absolute line number where TOC ends in this chunk, or -1 if TOC has not ended yet (still continuing)\n'
                '  "status": "searching" (no TOC found yet), "in_toc" (TOC started but not ended), or "done" (TOC ended)\n\n'
                "Rules:\n"
                "- If status was 'in_toc' coming in and TOC continues through this whole chunk: toc_start=-1, toc_end=-1, status='in_toc'\n"
                "- If status was 'in_toc' and TOC ends in this chunk: toc_start=-1, toc_end=<line>, status='done'\n"
                "- If TOC starts and ends in this chunk: set both toc_start and toc_end, status='done'\n"
                "- If TOC starts but does not end: toc_start=<line>, toc_end=-1, status='in_toc'\n"
                "- If no TOC in this chunk: toc_start=-1, toc_end=-1, status='searching'\n"
                "Return ONLY the JSON object, no explanation.\n\n"
                f"CHUNK:\n{numbered}"
            )

            message = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            result = json.loads(raw)
            chunk_status = result.get("status", "searching")
            chunk_toc_start = result.get("toc_start", -1)
            chunk_toc_end = result.get("toc_end", -1)

            print(
                f"INFO: chunk {chunk_start}-{chunk_start+len(chunk)-1}: "
                f"status={chunk_status}, toc_start={chunk_toc_start}, toc_end={chunk_toc_end}",
                file=sys.stderr,
            )

            if toc_start_abs is None and chunk_toc_start >= 0:
                toc_start_abs = chunk_toc_start
            if chunk_toc_end >= 0:
                toc_end_abs = chunk_toc_end

            status = chunk_status
            if status == "done":
                break

            chunk_start += _CHUNK_SIZE

        if toc_start_abs is None:
            return None

        if toc_end_abs is None:
            toc_end_abs = min(chunk_start + _CHUNK_SIZE, len(lines)) - 1

        while toc_end_abs > toc_start_abs and not lines[toc_end_abs].strip():
            toc_end_abs -= 1

        return TOCBoundary(
            start_line=toc_start_abs,
            end_line=toc_end_abs,
            marker="(agent-detected)",
        )
