# Miner-MinerU Development Guidelines

## Active Technologies
- Python 3.11+ (conda `agent` environment)
- Anthropic Claude API (LLM-based classification)
- stdlib only: `json`, `difflib`, `os`, `pathlib`

## Project Structure

```text
docstruct/              # Unified Python package
  agents/                  # One agent per concern
    base.py                # BaseAgent ABC, AgentResult, AgentChain
    boundary_agent.py      # TOC boundary detection
    classifier_agent.py    # TOC entry classification
    summary_agent.py       # Document summary generation
    metadata_agent.py      # Document metadata extraction
  models/                  # Pure data models
    document.py            # HeadingEntry, TOCBoundary, DocumentMetadata
    results.py             # ExtractionResult, LogEntry
  config/                  # Unified configuration
    __init__.py            # ProcessingConfig, AgentConfig
  exceptions.py            # MinerUError hierarchy (17 exception classes)
  pipeline/                # Orchestration and utilities
    extractor.py           # extract_toc() — runs all agents in sequence
    reader.py              # File I/O and content slicing
    heading_map.py         # Nested tree builder
    rule_engine.py         # Rule-based heading classifier
    md_fixer.py            # Markdown fixer: normalize headings using TOC
  providers/               # LLM backend abstraction
    factory.py             # build_client() — reads LLM_PROVIDER env var
    anthropic.py           # Anthropic Claude client
    azure.py               # Azure OpenAI wrapper
  cli/
    main.py                # CLI entry point (extract, fix subcommands)
  __init__.py              # Public API
  __main__.py              # python -m docstruct
scripts/                   # Runner scripts
  run_pipeline.py          # Full pipeline (extract + fix)
  run_fixer.py             # Fix-only (requires pre-extracted TOC)
  run_pipeline_all.py      # Batch: process all files in data/
tests/
  conftest.py              # Shared fixtures
  fixtures/                # Test data (sample_source.md, sample_toc.json)
  golden/                  # Golden JSON fixtures for integration tests
docs/
  architecture/            # Architecture and design docs
  guides/                  # User guides and quick starts
data/                      # Input documents
output/                    # Pipeline output (gitignored)
specs/                     # Feature specifications
```

## Commands

```bash
# Run tests (conda agent env, bypass anyio SSL issue)
PYTHONNOUSERSITE=1 "/c/Users/ERO8OFO/.conda/envs/agent/python.exe" -m pytest -p no:anyio

# Extract TOC from markdown
python -m docstruct extract <markdown_file> --output <output.json>

# Fix markdown heading levels using extracted TOC
python -m docstruct fix <source.md> --toc <toc.json> --output-dir <output/fixed>

# Batch pipeline (all files in data/)
python scripts/run_pipeline_all.py
```

## Code Style

Python 3.11+: Follow standard conventions. No unnecessary abstractions.

## File Organization Rules

**IMPORTANT**: Keep root directory clean.

### Files Allowed in Root
- `README.md`, `CLAUDE.md`, `.gitignore`, `requirements.txt`
- `.env` / `.env.example` — environment configuration
- `pyproject.toml` / `setup.py` — package configuration

### Where Things Go

| Type | Location |
|------|----------|
| Feature specifications | `specs/` |
| Documentation | `docs/` |
| Runner scripts | `scripts/` |
| Test fixtures | `tests/fixtures/` |
| Data files | `data/` |
| Output/results | `output/` |
| Code | `docstruct/` |
| Tests | `tests/` |

### DO NOT Create in Root
- Documentation files (`.md`, `.txt`) — use `docs/`
- Runner scripts (`.py`, `.sh`, `.bat`) — use `scripts/`
- Temporary/planning files — delete when done
