"""
LLM-based heading matcher for robust TOC-to-source matching.

Handles noisy cases: numbering mismatches, separator variations, OCR artifacts,
body text glued to headings, embedded headings in paragraphs, etc.

Used as a fallback after fast exact/fuzzy matching strategies fail.
"""

import json
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass


@dataclass
class LLMHeadingMatch:
    """Result of LLM matching for a single line."""
    line_number: int
    toc_index: Optional[int]  # Index in TOC entries, or None if no match
    heading_text: str  # Extracted heading (without body text)
    body_text: str  # Body text if present and separated from heading
    confidence: float  # 0.0-1.0


class LLMHeadingMatcher:
    """Match unmatched TOC entries to source lines using LLM."""

    def __init__(self, client):
        """Initialize with LLM client."""
        self._client = client

    def match_unmatched_headings(
        self,
        toc_entries: List[Dict],  # [{title, numbering, kind, ...}, ...]
        candidate_lines: List[Tuple[int, str]],  # [(line_number, raw_text), ...]
        matched_line_numbers: set,  # Already matched line numbers to skip
    ) -> List[LLMHeadingMatch]:
        """
        Use LLM to match unmatched TOC entries to candidate lines.

        Args:
            toc_entries: List of TOC entries with title, numbering, etc.
            candidate_lines: List of (line_number, raw_text) tuples to evaluate
            matched_line_numbers: Set of already-matched line numbers (to skip)

        Returns:
            List of LLMHeadingMatch results
        """
        # Filter to only unmmatched lines
        unmmatched_candidates = [
            (ln, text)
            for ln, text in candidate_lines
            if ln not in matched_line_numbers
        ]

        if not unmmatched_candidates:
            return []

        # Build the prompt
        toc_json = json.dumps(
            [
                {
                    "index": i,
                    "numbering": e.get("numbering"),
                    "title": e.get("title"),
                    "kind": e.get("kind"),
                }
                for i, e in enumerate(toc_entries)
            ],
            indent=2,
        )

        candidates_text = "\n".join(
            [f"Line {ln}: {text}" for ln, text in unmmatched_candidates]
        )

        prompt = f"""You are matching source document lines to a Table of Contents.

TOC ENTRIES (with index):
{toc_json}

CANDIDATE LINES (from source document):
{candidates_text}

For EACH candidate line:
1. Determine if it contains a heading that matches one of the TOC entries
2. If yes: extract the HEADING TEXT and any BODY TEXT that follows
3. If no: mark as no match

MATCHING RULES:
- Match by numbering (Art. 19, Art. 20, etc.) or title text
- Handle variations: missing/different numbering, typos, OCR errors
- Detect body text: if heading is followed by space and capital letter, that's body start
- Example: "Art. 19 - Information references For information on this..."
  → heading="Art. 19 - Information references", body="For information on this..."

Return ONLY a JSON array of objects, no explanation:
{{
  "line_number": <int>,
  "toc_index": <int or null>,
  "heading_text": "<extracted heading or full line if no body>",
  "body_text": "<body text if separated, else empty string>",
  "confidence": <0.0-1.0>
}}

Focus on robustness: handle numbering off-by-one, missing separators, glued text."""

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # Remove markdown code fence if present
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        results_data = json.loads(raw)
        return [
            LLMHeadingMatch(
                line_number=item["line_number"],
                toc_index=item.get("toc_index"),
                heading_text=item.get("heading_text", ""),
                body_text=item.get("body_text", ""),
                confidence=item.get("confidence", 0.5),
            )
            for item in results_data
        ]

    def batch_match(
        self,
        toc_entries: List[Dict],
        unmatched_headings_with_lines: List[Tuple[int, str]],  # [(line_num, text), ...]
        matched_line_numbers: set,
    ) -> Dict[int, Tuple[Optional[int], str, str]]:
        """
        Batch match unmatched headings.

        Returns:
            {line_number: (toc_index, heading_text, body_text)}
            where toc_index is None if no match found.
        """
        matches = self.match_unmatched_headings(
            toc_entries, unmatched_headings_with_lines, matched_line_numbers
        )

        result = {}
        for match in matches:
            if match.toc_index is not None:
                result[match.line_number] = (
                    match.toc_index,
                    match.heading_text,
                    match.body_text,
                )
            else:
                result[match.line_number] = (None, match.heading_text, match.body_text)

        return result
