# DocStruct Development Guidelines

## Active Technologies
- Python 3.9+ (env: `py_latest`, Python 3.13) + `neo4j>=5.11`, `openai` (existing), `cohere>=5.0` (new), `python-dotenv` (existing), `langgraph` (existing), `pytest` (existing) (005-neo4j-hybrid-search)
- Embedding providers: OpenAI (text-embedding-3-small/large), Cohere (embed-english-v3.0), Azure OpenAI (deployment-based)
- Neo4j 5.x (graph + full-text + vector indexes); `.pageindex.json` files remain source of truth (005-neo4j-hybrid-search)

- Python 3.9+
- `anthropic`, `openai`, `python-dotenv`
- File-based markdown and JSON processing

## Project Structure

```text
src/docstruct/
  domain/            # Pure business logic and models
  application/       # Use cases, ports, agents
  infrastructure/    # LLM adapters and file I/O
  interfaces/        # CLI
tools/               # Local runner scripts
tests/               # Pytest suite
docs/                # Architecture and usage notes
data/                # Input documents
output/              # Generated artifacts
```

## Commands

```bash
PYTHONNOUSERSITE=1 python -m pytest -p no:anyio
python -m docstruct extract <markdown_file> --output <output.json>
python -m docstruct fix <source.md> --toc <toc.json> --output-dir <output/fixed>
python tools/run_pipeline_all.py
```

## Rules

Detailed coding standards live in `.claude/rules.md`.

## File Organization

- Code belongs under `src/`
- Runner scripts belong under `tools/`
- Documentation belongs under `docs/`
- Specs belong under `specs/`
- Keep root-level files limited to core project metadata and entry docs
