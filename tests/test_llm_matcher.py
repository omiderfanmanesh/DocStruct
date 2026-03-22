#!/usr/bin/env python
"""Tests and manual harness for the LLM heading matcher."""

import json
from unittest.mock import MagicMock

from docstruct.application.agents.llm_heading_matcher import LLMHeadingMatcher
from docstruct.infrastructure.llm.factory import build_client

# Sample noisy data
TOC_ENTRIES = [
    {
        "index": 0,
        "numbering": "Art. 18",
        "title": "Information references",
        "kind": "article",
    },
    {
        "index": 1,
        "numbering": "Art. 19",
        "title": "Regulatory references",
        "kind": "article",
    },
]

# These are the actual noisy lines from the Bando document
CANDIDATE_LINES = [
    (804, "Art. 18 – Information on the processing of personal data"),
    (822, "Art. 19 - Information references For information on this call, contact the Financial Aid Office (c/o Palazzo Ca' Foscari - Dorsoduro, 3246 - 30123 Venice) of the Teaching and Student Services Area, Office of Student Careers and Right to Education via:"),
    (831, "Art. 20 - Regulatory references University Statute Rector's Decree no. 750 of 8 September 2011 and subsequent amendments and additions..."),
]


def test_batch_match_splits_large_candidate_sets():
    client = MagicMock()
    client.create_message.side_effect = [
        json.dumps(
            [
                {
                    "line_number": 1,
                    "toc_index": 0,
                    "heading_text": "Heading 1",
                    "body_text": "",
                    "confidence": 0.9,
                }
            ]
        ),
        "```json\n[]\n```",
    ]
    matcher = LLMHeadingMatcher(client)
    candidates = [(index, f"Line {index}") for index in range(1, 25)]

    result = matcher.batch_match([TOC_ENTRIES[0]], candidates, set())

    assert client.create_message.call_count == 2
    assert result[1][0] == 0

def main():
    try:
        client = build_client()
    except SystemExit:
        print("ERROR: LLM client not available. Set ANTHROPIC_API_KEY to test.")
        print("(Fast matching still works without API key)")
        return

    print("Testing LLM-based heading matcher on noisy TOC entries...\n")

    matcher = LLMHeadingMatcher(client)
    matched = matcher.match_unmatched_headings(TOC_ENTRIES, CANDIDATE_LINES, set())

    for match in matched:
        print(f"Line {match.line_number}:")
        print(f"  TOC Index: {match.toc_index}")
        print(f"  Heading: {match.heading_text}")
        if match.body_text:
            print(f"  Body (truncated): {match.body_text[:80]}...")
        print(f"  Confidence: {match.confidence:.1%}\n")


if __name__ == "__main__":
    main()
