"""ClassifierAgent: classify TOC entries via LLM."""

from __future__ import annotations

import json
import re
import sys

from docstruct.application.ports import LLMPort
from docstruct.config import AgentConfig
from docstruct.domain.models import HeadingEntry


_CHUNK_LINES = 50

_INSTRUCTIONS = (
    "You are processing a Table of Contents from a PDF-extracted legal/academic PDF.\n\n"
    "Below is a portion of the raw TOC text. Classify every entry and return only JSON.\n\n"
)


class ClassifierAgent:
    def __init__(self, client: LLMPort):
        self._client = client
        self._model = AgentConfig.from_env().model

    def _classify_chunk(self, chunk_text: str) -> list[dict]:
        raw = self._client.create_message(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": _INSTRUCTIONS + f"TOC TEXT:\n{chunk_text}"}],
        ).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM response was truncated or malformed (JSON error: {exc}). "
                f"Try reducing _CHUNK_LINES below {_CHUNK_LINES}."
            ) from exc

    def run(self, toc_text: str) -> list[HeadingEntry]:
        lines = toc_text.splitlines()
        chunks = [lines[index : index + _CHUNK_LINES] for index in range(0, len(lines), _CHUNK_LINES)]
        all_items: list[dict] = []
        for index, chunk_lines in enumerate(chunks, start=1):
            if len(chunks) > 1:
                print(f"  Classifying chunk {index}/{len(chunks)} ({len(chunk_lines)} lines)...", file=sys.stderr)
            all_items.extend(self._classify_chunk("\n".join(chunk_lines)))
        return [
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
            for item in all_items
        ]
