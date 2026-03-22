"""BoundaryAgent — sliding 50-line window: extracts TOC entries and detects end of TOC."""
from __future__ import annotations

import json
import re
import sys

from docstruct.models.document import HeadingEntry, TOCBoundary

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
- "in_toc": these lines are part of the TOC — return all entries found
- "done": the TOC ended in these lines — body text (prose, paragraphs, legal clauses) has started.
           Return only entries found BEFORE the body started.

TOC entries are lines that list document sections, articles, or headings.
Body text is prose: full sentences, definitions, "Dear student,", legal clauses, paragraphs.

For each TOC entry return:
  "title": heading text without numbering or page number
  "kind": "section" | "article" | "subarticle" | "annex" | "topic"
  "numbering": prefix like "ART. 1", "SECTION I", "1.2" or null
  "separator": separator between numbering and title (e.g. " ", " - ", " – ") or null
  "pattern": full heading = numbering + separator + title (or just title if no numbering)
  "page": trailing page number as integer or null
  "depth": 1=section, 2=article, 3+=subarticle
  "confidence": 0.0–1.0

Classification rules:
- SECTION / SEZIONE / SECTION I–XI → kind=section, depth=1
- ART. N / Art. N / ARTICLE N → kind=article, depth=2
- ART. N(M) / Art. N(M) / Art. N paragraph M → kind=subarticle, depth=3
- Art. N(M.K) → kind=subarticle, depth=4
- ANNEX / ALLEGATO → kind=annex, depth=1
- Unnumbered ALL-CAPS or title-case headings → kind=topic, depth=2

Return ONLY this JSON object, no explanation:
{"status": "pre_toc" | "in_toc" | "done", "entries": [...]}

LINES:
"""


class BoundaryAgent:
    """Slides a 50-line window over the document, extracting TOC entries until body text starts."""

    def __init__(self, client):
        self._client = client

    def run(self, lines: list[str]) -> tuple[TOCBoundary | None, list[HeadingEntry]]:
        """
        Return (TOCBoundary, entries) where entries are all classified TOC entries.
        Returns (None, []) if no TOC found.
        """
        scan_lines = lines[:_MAX_SCAN_LINES]

        toc_start_abs: int | None = None
        toc_end_abs: int | None = None
        all_entries: list[HeadingEntry] = []

        chunk_start = 0
        while chunk_start < len(scan_lines):
            chunk = scan_lines[chunk_start: chunk_start + _CHUNK_SIZE]
            numbered = "".join(
                f"[{chunk_start + i}] {line}" for i, line in enumerate(chunk)
            )

            message = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=8192,
                messages=[{"role": "user", "content": _PROMPT + numbered}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            result = json.loads(raw)
            status = result.get("status", "pre_toc")
            entries = result.get("entries", [])

            chunk_end = chunk_start + len(chunk) - 1
            print(
                f"  Scanning lines {chunk_start}–{chunk_end}: {status}"
                + (f" ({len(entries)} entries)" if entries else ""),
                file=sys.stderr,
            )

            if status == "pre_toc":
                chunk_start += _CHUNK_SIZE
                continue

            if status in ("in_toc", "done"):
                if toc_start_abs is None:
                    toc_start_abs = chunk_start

                for item in entries:
                    all_entries.append(HeadingEntry(
                        title=item.get("title", ""),
                        kind=item.get("kind", "topic"),
                        depth=item.get("depth", 2),
                        numbering=item.get("numbering"),
                        separator=item.get("separator"),
                        pattern=item.get("pattern"),
                        page=item.get("page"),
                        confidence=item.get("confidence"),
                    ))

                if status == "done":
                    toc_end_abs = chunk_end
                    break

            chunk_start += _CHUNK_SIZE

        if toc_start_abs is None:
            return None, []

        if toc_end_abs is None:
            toc_end_abs = chunk_start + _CHUNK_SIZE - 1

        boundary = TOCBoundary(
            start_line=toc_start_abs,
            end_line=toc_end_abs,
            marker="(agent-detected)",
        )
        return boundary, all_entries
