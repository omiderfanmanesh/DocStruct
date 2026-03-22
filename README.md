# DocStruct

TOC extraction and markdown-fixing pipeline for structured document markdown.

## Quick Start

```bash
python -m pip install -e .

# Extract TOC JSON
python -m docstruct extract data/document.md --output output/document.json

# Fix headings using extracted TOC
python -m docstruct fix data/document.md --toc output/document.json --output-dir output/fixed
```

## Project Layout

```text
src/docstruct/
  domain/          # Pure models and matching logic
  application/     # Use cases and agents
  infrastructure/  # LLM adapters and file I/O
  interfaces/      # CLI entry points

tools/             # Batch/helper scripts
tests/             # Test suite
data/              # Input markdown
output/            # Generated JSON and fixed markdown
docs/              # Supporting guides and architecture notes
```

## Helper Scripts

```bash
python tools/run_extract.py data/document.md
python tools/run_extract_all.py
python tools/run_fix.py data/document.md --toc output/document.json
python tools/run_pipeline_all.py
python tools/run_pipeline.py
python tools/run_fixer.py
python tools/smoke_test.py data/document.md
```

## Environment

`LLM_PROVIDER` defaults to `anthropic`.

Supported provider variables:

- `ANTHROPIC_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

DocStruct-specific settings use the `DOCSTRUCT_` prefix, for example:

- `DOCSTRUCT_MIN_CONFIDENCE`
- `DOCSTRUCT_BATCH_SIZE`
- `DOCSTRUCT_AGENT_MODEL`

## Tests

```bash
PYTHONNOUSERSITE=1 python -m pytest -p no:anyio
```

## Runtime

Python 3.9+.
