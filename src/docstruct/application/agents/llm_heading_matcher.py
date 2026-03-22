"""LLM-based fallback matcher for noisy heading lines."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from docstruct.application.ports import LLMPort


@dataclass
class LLMHeadingMatch:
    line_number: int
    toc_index: int | None
    heading_text: str
    body_text: str
    confidence: float


class LLMHeadingMatcher:
    _BATCH_SIZE = 20

    def __init__(self, client: LLMPort):
        self._client = client

    @staticmethod
    def _strip_fences(raw: str) -> str:
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        return raw

    @classmethod
    def _parse_matches(cls, raw: str) -> list[dict]:
        cleaned = cls._strip_fences(raw.strip())
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start >= 0 and end > start:
                parsed = json.loads(cleaned[start : end + 1])
                return parsed if isinstance(parsed, list) else []
            raise

    def match_unmatched_headings(
        self,
        toc_entries: list[dict],
        candidate_lines: list[tuple[int, str]],
        matched_line_numbers: set[int],
    ) -> list[LLMHeadingMatch]:
        unmatched_candidates = [
            (line_number, text)
            for line_number, text in candidate_lines
            if line_number not in matched_line_numbers
        ]
        if not unmatched_candidates:
            return []

        toc_json = json.dumps(
            [
                {
                    "index": index,
                    "numbering": entry.get("numbering"),
                    "title": entry.get("title"),
                    "kind": entry.get("kind"),
                }
                for index, entry in enumerate(toc_entries)
            ],
            indent=2,
        )
        candidates_text = "\n".join(f"Line {line_number}: {text}" for line_number, text in unmatched_candidates)
        raw = self._client.create_message(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are matching source document lines to a table of contents.\n\n"
                        f"TOC ENTRIES:\n{toc_json}\n\n"
                        f"CANDIDATE LINES:\n{candidates_text}\n\n"
                        "Return only a JSON array with line_number, toc_index, heading_text, body_text, confidence."
                    ),
                }
            ],
        ).strip()
        return [
            LLMHeadingMatch(
                line_number=item["line_number"],
                toc_index=item.get("toc_index"),
                heading_text=item.get("heading_text", ""),
                body_text=item.get("body_text", ""),
                confidence=item.get("confidence", 0.5),
            )
            for item in self._parse_matches(raw)
        ]

    def batch_match(
        self,
        toc_entries: list[dict],
        unmatched_headings_with_lines: list[tuple[int, str]],
        matched_line_numbers: set[int],
    ) -> dict[int, tuple[int | None, str, str]]:
        result: dict[int, tuple[int | None, str, str]] = {}
        for start in range(0, len(unmatched_headings_with_lines), self._BATCH_SIZE):
            batch = unmatched_headings_with_lines[start : start + self._BATCH_SIZE]
            matches = self.match_unmatched_headings(
                toc_entries,
                batch,
                matched_line_numbers.union(result.keys()),
            )
            for match in matches:
                result[match.line_number] = (match.toc_index, match.heading_text, match.body_text)
        return result
