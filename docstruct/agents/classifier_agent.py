"""ClassifierAgent — classifies TOC entries via LLM."""
from __future__ import annotations

import json
import re

from docstruct.models.document import HeadingEntry


class ClassifierAgent:
    """Sends the TOC text block to the LLM and returns classified HeadingEntry objects."""

    def __init__(self, client):
        self._client = client

    def run(self, toc_text: str) -> list[HeadingEntry]:
        prompt = (
            "You are processing a Table of Contents from a MinerU-extracted legal/academic PDF.\n\n"
            "Below is the raw TOC text. Classify EVERY entry (skip the header line itself).\n\n"
            "For each line that is a TOC entry, return a JSON object with:\n"
            '  "title": the heading text (without numbering or page number)\n'
            '  "kind": one of "section", "article", "subarticle", "annex", "topic"\n'
            '  "numbering": the numbering prefix if present (e.g. "Art. 1", "ARTICLE 1", "1.2.3"), else null\n'
            '  "separator": the exact separator string between numbering and title as it appears '
            'in the TOC (e.g. " – ", " - ", " ", ": "). null if no numbering.\n'
            '  "pattern": the full canonical heading text to search in the document body, built as '
            'numbering + separator + title, or just title when there is no numbering\n'
            '  "page": the trailing page number as integer if present, else null\n'
            '  "depth": 1 for section, 2 for article, 3+ for subarticle (based on nesting)\n'
            '  "confidence": your confidence 0.0-1.0\n\n'
            "Return ONLY a JSON array of objects, no explanation, no markdown fences.\n\n"
            "Classification rules:\n"
            "- SECTION / SEZIONE / SECTION I-XI → kind=section, depth=1\n"
            "- Art. N / ART. N / Articolo N / ARTICLE N → kind=article, depth=2\n"
            "- Art. N(M) / ART. N(M) → kind=subarticle, depth=3\n"
            "- Art. N paragraph M.M → kind=subarticle, depth=4\n"
            '- N.N / N.N.N decimal entries → kind=subarticle, depth=3 for N.N, depth=4 for N.N.N\n'
            '- ANNEX / ALLEGATO / ANNEX "X" → kind=annex, depth=1\n'
            "- Short ALL-CAPS lines or title-case headings with no numbering → kind=topic, depth=2\n\n"
            "Separator examples:\n"
            '- "ARTICLE 1 – Some Title" → separator=" – "\n'
            '- "Art. 1 - Some Title" → separator=" - "\n'
            '- "1.1 Some Title" → separator=" "\n'
            '- "ANNEX A: Some Title" → separator=": "\n\n'
            f"TOC TEXT:\n{toc_text}"
        )

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        entries_data = json.loads(raw)
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
            for item in entries_data
        ]
