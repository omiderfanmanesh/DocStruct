#!/usr/bin/env python
"""
Test script: LLM-based heading matcher on noisy TOC entries.

This demonstrates the LLM matcher handling:
- Numbering mismatches (TOC says Art. 18, source says Art. 19)
- Glued heading+body text
- Separator variations
"""

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
