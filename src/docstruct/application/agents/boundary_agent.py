"""BoundaryAgent: sliding TOC detection and entry extraction."""

from __future__ import annotations

import json
import re
import sys

from docstruct.application.ports import LLMPort
from docstruct.domain.models import HeadingEntry, TOCBoundary


_CHUNK_SIZE = 50
_MAX_SCAN_LINES = 800

_PROMPT = """\
You are processing a document extracted from a PDF.

Below are document lines with their absolute line numbers in [brackets].
Your task:
1. Extract all Table of Contents (TOC) entries present in these lines
2. Report the status of these lines

Status:
- "pre_toc": TOC has not started yet (title page, preamble, introduction, etc.)
- "in_toc": these lines are part of the TOC; return all entries found
- "done": the TOC ended in these lines; body text (prose, paragraphs, legal clauses) has started.
          Return only entries found BEFORE the body started.

Return ONLY this JSON object, no explanation:
{"status": "pre_toc" | "in_toc" | "done", "entries": [...]}

LINES:
"""


class BoundaryAgent:
    def __init__(self, client: LLMPort):
        self._client = client

    def run(self, lines: list[str]) -> tuple[TOCBoundary | None, list[HeadingEntry]]:
        scan_lines = lines[:_MAX_SCAN_LINES]
        toc_start_abs: int | None = None
        toc_end_abs: int | None = None
        all_entries: list[HeadingEntry] = []

        chunk_start = 0
        while chunk_start < len(scan_lines):
            chunk = scan_lines[chunk_start : chunk_start + _CHUNK_SIZE]
            numbered = "".join(f"[{chunk_start + index}] {line}" for index, line in enumerate(chunk))
            raw = self._client.create_message(
                model="claude-haiku-4-5-20251001",
                max_tokens=8192,
                messages=[{"role": "user", "content": _PROMPT + numbered}],
            ).strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            result = json.loads(raw)
            status = result.get("status", "pre_toc")
            entries = result.get("entries", [])
            response_start = result.get("toc_start")
            response_end = result.get("toc_end")
            chunk_end = chunk_start + len(chunk) - 1
            print(
                f"  Scanning lines {chunk_start}-{chunk_end}: {status}" + (f" ({len(entries)} entries)" if entries else ""),
                file=sys.stderr,
            )

            if status == "pre_toc":
                chunk_start += _CHUNK_SIZE
                continue

            if status in {"in_toc", "done"}:
                if toc_start_abs is None:
                    if isinstance(response_start, int) and response_start >= 0:
                        toc_start_abs = response_start
                    else:
                        toc_start_abs = chunk_start
                for item in entries:
                    all_entries.append(
                        HeadingEntry(
                            title=item.get("title", ""),
                            kind=item.get("kind", "topic"),
                            depth=item.get("depth", 2),
                            numbering=item.get("numbering"),
                            separator=item.get("separator"),
                            pattern=item.get("pattern"),
                            page=item.get("page"),
                            confidence=item.get("confidence"),
                        )
                    )
                if status == "done":
                    if isinstance(response_end, int) and response_end >= 0:
                        toc_end_abs = response_end
                    else:
                        toc_end_abs = chunk_end
                    break

            chunk_start += _CHUNK_SIZE

        if toc_start_abs is None:
            return None, []
        if toc_end_abs is None:
            toc_end_abs = min(len(scan_lines) - 1, chunk_start + _CHUNK_SIZE - 1)
        return TOCBoundary(start_line=toc_start_abs, end_line=toc_end_abs, marker="(agent-detected)"), all_entries
