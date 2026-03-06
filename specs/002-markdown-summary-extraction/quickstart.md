# Quickstart: TOC Extraction Agent

## Prerequisites

- Python 3.11+ (conda `agent` environment)
- Anthropic API key set as `ANTHROPIC_API_KEY` environment variable
- MinerU-generated markdown file(s) in `data/` directory

## Setup

```bash
conda activate agent
pip install anthropic
```

## Usage

### Extract TOC from a single document

```bash
python scripts/toc_extraction_agent.py "data/Notice_of_competition_scholarship_accommodation_and_degree_award_a.y.2025.26_2026/MinerU_markdown_Notice_of_competition_scholarship_accommodation_and_degree_award_a.y.2025.26_2026957185039605760.md"
```

### Save output to file

```bash
python scripts/toc_extraction_agent.py "data/Notice_of_competition.../MinerU_markdown_*.md" --output output/notice_toc.json
```

### Run tests

```bash
pytest tests/test_toc_extraction.py -v
```

## What it does

1. Reads the MinerU markdown file
2. Finds the TOC section (looks for `# Summary`, `# TABLE OF CONTENTS`, `# Sommario`)
3. Sends the TOC text to Claude for classification (section/article/subarticle)
4. Outputs structured JSON with heading hierarchy, metadata, summary, and boundaries

## Output

JSON file with:
- `toc` — flat list of classified heading entries
- `heading_map` — nested tree structure (section → article → subarticle)
- `summary` — 2-3 sentence document summary
- `metadata` — title, year, document type, organization
- `toc_boundaries` — start/end line numbers of TOC section
- `processing_log` — classification decisions for auditability
