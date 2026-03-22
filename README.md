# DocStruct

TOC extraction and markdown-fixing pipeline for structured document markdown.

The LLM backend uses LangChain chat-model adapters, and the multi-step PageIndex QA flow is orchestrated with LangGraph.

## Quick Start

```bash
python -m pip install -e .

# Extract TOC JSON
python -m docstruct extract data/document.md --output output/01_toc/document.json

# Fix headings using extracted TOC
python -m docstruct fix data/document.md --toc output/01_toc/document.json --output-dir output/02_fixed_markdown --report-dir output/02_fix_reports

# Build PageIndex-backed search indexes from fixed markdown
python -m docstruct index output/02_fixed_markdown --output-dir output/03_pageindex --toc-dir output/01_toc

# Ask grounded questions across indexed documents
python -m docstruct ask "What are the application deadlines?" --index-dir output/03_pageindex
```

## Docker

The repo now includes a `Dockerfile` and `compose.yaml` so you can run the CLI without a local Python setup.
Create `.env` from `.env.example`, then run:

```bash
docker compose build
docker compose run --rm docstruct extract data/document.md --output output/01_toc/document.json
docker compose run --rm docstruct fix data/document.md --toc output/01_toc/document.json --output-dir output/02_fixed_markdown --report-dir output/02_fix_reports
docker compose run --rm docstruct index output/02_fixed_markdown --output-dir output/03_pageindex --toc-dir output/01_toc
docker compose run --rm docstruct ask "What are the application deadlines?" --index-dir output/03_pageindex
```

`docker compose` mounts the local `data/` and `output/` folders into the container, so inputs and generated artifacts stay in the repo on your machine.

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
python tools/run_fix.py data/document.md --toc output/01_toc/document.json
python tools/run_pipeline_all.py
python tools/run_pipeline.py
python tools/run_pageindex.py
python tools/run_search_agent.py "What are the deadlines?"
python tools/run_fixer.py
python tools/smoke_test.py data/document.md
```

`tools/run_pipeline_all.py` now builds PageIndex-backed search indexes in `output/03_pageindex/` after markdown fixing unless `--skip-index` is provided.

## Environment

`LLM_PROVIDER` defaults to `anthropic`.

Supported provider variables:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`

DocStruct-specific settings use the `DOCSTRUCT_` prefix, for example:

- `DOCSTRUCT_MIN_CONFIDENCE`
- `DOCSTRUCT_BATCH_SIZE`
- `DOCSTRUCT_AGENT_MODEL`

If you use `LLM_PROVIDER=openai`, DocStruct will default the agent model from `OPENAI_MODEL` and fall back to `gpt-4.1-mini` when `DOCSTRUCT_AGENT_MODEL` is not set.

## PageIndex Workflow

DocStruct now supports a grounded document-QA workflow that uses a vendored, markdown-only PageIndex-compatible tree builder inside the project. No separate PageIndex checkout is required at runtime.

1. Run the normal extract/fix pipeline.
2. Build indexes with `python -m docstruct index output/02_fixed_markdown --output-dir output/03_pageindex`.
3. Ask questions with `python tools/run_search_agent.py "..." --index-dir output/03_pageindex`.

The batch runner handles step 2 automatically after `fix`.

The search agent now applies document-scope guardrails for multi-document collections. If a question could match different universities, regions, or issuers, it will ask for clarification instead of guessing across conflicting scholarship notices.

It also performs a HyPE-style retrieval rewrite before document selection: the agent expands short or vague user questions into a more explicit search query using only scope evidence found in the indexed documents, not from hardcoded region or university aliases.

Each indexed document now includes a compact `search_profile` used for low-token document ranking. The profile favors issuer, region, academic year, covered institutions, covered cities, and benefit types over long descriptive summaries.

For best reasoning quality, point `AZURE_OPENAI_DEPLOYMENT`, `OPENAI_MODEL`, or your Anthropic model setting at the strongest chat/reasoning model available in your environment rather than a mini-tier default.

## Output Layout

New pipeline artifacts are written into stage-specific folders:

- `output/01_toc/`
- `output/02_fixed_markdown/`
- `output/02_fix_reports/`
- `output/03_pageindex/`
- `output/04_answers/`
- `output/00_runs/`

## Tests

```bash
PYTHONNOUSERSITE=1 python -m pytest -p no:anyio
```

## Runtime

Python 3.9+.
