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
python tools/response_metrics.py
```

## Response Metrics

All SearchAnswer responses include execution metrics:
- **execution_time_seconds**: Actual time in seconds to process the query
- **tokens_used**: Estimated token count (~1 token ≈ 4 characters, with 1.2x overhead multiplier)
- **estimated_cost_usd**: Approximate USD cost based on Claude Haiku pricing:
  - Input: $0.80 per million tokens
  - Output: $4.00 per million tokens

**Example response with metrics:**
```json
{
  "question": "What documents are needed?",
  "answer": "Required documents are...",
  "citations": [...],
  "document_ids": [...],
  "execution_time_seconds": 2.34,
  "tokens_used": 3200,
  "estimated_cost_usd": 0.0089,
  ...
}
```

Metrics are calculated using `estimate_tokens()` and `calculate_cost()` from `infrastructure/metrics.py`.

## Rules

Detailed coding standards live in `.claude/rules.md`.

## File Organization

**STRICT RULE: Do NOT create files in the root directory. Always respect folder structure.**

- Code belongs under `src/`
- Runner scripts belong under `tools/`
- Documentation belongs under `docs/`
- Specs belong under `specs/`
- Unit tests belong under `tests/unit/`
- Integration tests belong under `tests/integration/`
- Test fixtures/data belong under `tests/fixtures/`
- Keep root-level files limited to core project metadata and entry docs (README, LICENSE, pyproject.toml, etc.)
- **Before creating any new file, verify the correct subdirectory exists. If unsure about placement, ask first.**
