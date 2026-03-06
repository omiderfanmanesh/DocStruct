# CLI Contract: TOC Extraction Agent

## Command

```
python scripts/toc_extraction_agent.py <markdown_file_path> [--output <output_path>]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `markdown_file_path` | yes | — | Path to MinerU-generated markdown file |
| `--output` | no | stdout | Path to write JSON output (if omitted, prints to stdout) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | File not found or unreadable |
| 2 | No TOC section detected |
| 3 | LLM API error |

## Output

JSON conforming to `ExtractionResult` schema (see [data-model.md](../data-model.md)).

### Example Output (abbreviated)

```json
{
  "toc": [
    {
      "title": "RECIPIENTS AND AMOUNTS",
      "kind": "section",
      "numbering": "SECTION I",
      "page": 10,
      "depth": 1,
      "confidence": 0.95
    },
    {
      "title": "COURSES AND UNIVERSITIES FOR WHICH BENEFITS ARE GRANTED",
      "kind": "article",
      "numbering": "Art. 1",
      "page": 11,
      "depth": 2,
      "confidence": 0.98
    },
    {
      "title": "COURSES",
      "kind": "subarticle",
      "numbering": "Art. 1(1)",
      "page": 11,
      "depth": 3,
      "confidence": 0.92
    }
  ],
  "heading_map": [
    {
      "title": "RECIPIENTS AND AMOUNTS",
      "kind": "section",
      "numbering": "SECTION I",
      "page": 10,
      "depth": 1,
      "children": [
        {
          "title": "COURSES AND UNIVERSITIES...",
          "kind": "article",
          "numbering": "Art. 1",
          "page": 11,
          "depth": 2,
          "children": [
            {
              "title": "COURSES",
              "kind": "subarticle",
              "numbering": "Art. 1(1)",
              "page": 11,
              "depth": 3,
              "children": []
            }
          ]
        }
      ]
    }
  ],
  "summary": "This is a notice of competition for scholarships, accommodation services, and degree awards for academic year 2025/26. It covers eligibility criteria, application procedures, and benefit amounts for students at Piedmont universities.",
  "metadata": {
    "title": "Notice of competition a.y. 2025/26",
    "year": "2025/26",
    "document_type": "Notice of competition",
    "organization": "EDISU Piemonte",
    "source": "explicit"
  },
  "toc_boundaries": {
    "start_line": 82,
    "end_line": 145,
    "marker": "# Summary"
  },
  "processing_log": [
    {"line": 82, "action": "detected", "detail": "TOC marker '# Summary' found"},
    {"line": 84, "action": "classified", "detail": "SECTION I → section (depth 1)"},
    {"line": 86, "action": "classified", "detail": "ART. 1 → article (depth 2)"}
  ],
  "extracted_at": "2026-03-06T10:30:00Z"
}
```

## Stderr

Structured log lines for observability:

```
INFO: Reading file: data/Notice_of_competition.../MinerU_markdown_*.md
INFO: TOC marker found at line 82: '# Summary'
INFO: TOC section spans lines 82-145
INFO: Sending 63 TOC lines to LLM for classification
INFO: Classified 28 entries (12 articles, 4 sections, 12 subarticles)
INFO: Extraction complete in 2.3s
```
