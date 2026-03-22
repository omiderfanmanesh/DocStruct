"""BoundaryAgent: sliding TOC detection and entry extraction."""

from __future__ import annotations

import json
import sys
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig
from docstruct.domain.models import HeadingEntry, TOCBoundary
from docstruct.infrastructure.llm.structured_output import invoke_structured


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

TOC entries are lines that list document sections, articles, or headings.
Body text is prose: full sentences, definitions, greetings, legal clauses, or paragraphs.

For each TOC entry return:
  "title": heading text without numbering or page number
  "kind": "section" | "article" | "subarticle" | "annex" | "topic"
  "numbering": prefix like "ART. 1", "SECTION I", "1.2" or null
  "separator": separator between numbering and title (for example " ", " - ", " – ") or null
  "pattern": full heading = numbering + separator + title, or just title if no numbering
  "page": trailing page number as integer or null
  "depth": 1=section, 2=article, 3+=subarticle
  "confidence": 0.0-1.0

Classification rules:
- SECTION / SEZIONE / PART / CHAPTER -> kind=section, depth=1
- ART. N / Art. N / ARTICLE N -> kind=article, depth=2
- ART. N(M) / Art. N(M) / Art. N paragraph M -> kind=subarticle, depth=3
- Decimal headings like 1.2 or 1.2.3 -> kind=subarticle, depth based on nesting
- ANNEX / ALLEGATO -> kind=annex, depth=1
- Unnumbered all-caps or title-case headings -> kind=topic, depth=2

Return ONLY this JSON object, no explanation:
{"status": "pre_toc" | "in_toc" | "done", "entries": [...]}

LINES:
"""


class _BoundaryPayload(BaseModel):
    status: str = "pre_toc"
    entries: List[Any] = Field(default_factory=list)
    toc_start: Optional[int] = None
    toc_end: Optional[int] = None


class BoundaryAgent:
    def __init__(self, client: LLMPort):
        self._client = client
        self._model = AgentConfig.from_env().model

    @staticmethod
    def _coerce_line_number(value) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
        return None

    @staticmethod
    def _normalize_entry(item) -> dict:
        if isinstance(item, dict):
            return item

        if isinstance(item, str):
            stripped = item.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return {
                    "title": stripped,
                    "kind": "topic",
                    "depth": 2,
                    "pattern": stripped,
                }
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                return {
                    "title": parsed,
                    "kind": "topic",
                    "depth": 2,
                    "pattern": parsed,
                }
        return {}

    @classmethod
    def _normalize_entries(cls, entries) -> list[dict]:
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            return []
        return [entry for entry in (cls._normalize_entry(item) for item in entries) if entry]

    def run(self, lines: list[str]) -> tuple[TOCBoundary | None, list[HeadingEntry]]:
        scan_lines = lines[:_MAX_SCAN_LINES]
        toc_start_abs: int | None = None
        toc_end_abs: int | None = None
        all_entries: list[HeadingEntry] = []

        chunk_start = 0
        while chunk_start < len(scan_lines):
            chunk = scan_lines[chunk_start : chunk_start + _CHUNK_SIZE]
            numbered = "".join(f"[{chunk_start + index}] {line}" for index, line in enumerate(chunk))
            result = invoke_structured(
                self._client,
                model=self._model,
                max_tokens=8192,
                messages=[{"role": "user", "content": _PROMPT + numbered}],
                schema=_BoundaryPayload,
            )
            status = result.status
            entries = self._normalize_entries(list(result.entries))
            response_start = self._coerce_line_number(result.toc_start)
            response_end = self._coerce_line_number(result.toc_end)
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
                    if response_start is not None and response_start >= 0:
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
                    if response_end is not None and response_end >= 0:
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
