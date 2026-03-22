# DocStruct Development Guidelines

## Active Technologies

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
