# Miner-MinerU Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-06

## Active Technologies
- Python 3.11+ (conda `agent` environment) + `json` (stdlib), `difflib` (stdlib for fuzzy matching), `os`/`pathlib` (stdlib) (002-fix-source-markdown)
- File-based — reads source `.md` + output `.json`, writes corrected `.md` + report `.json` to `output/fixed/` (002-fix-source-markdown)

- Python 3.11+ (conda `agent` environment) + Anthropic Claude API (for LLM-based classification), `json` stdlib (002-markdown-summary-extraction)

## Project Structure

```text
miner_mineru/              # Main Python package
  agents/                  # One LLM agent per concern
    boundary_agent.py      # Sliding-window TOC boundary detection
    classifier_agent.py    # TOC entry classification
    summary_agent.py       # Document summary generation
    metadata_agent.py      # Document metadata extraction
  models/                  # Pure data models (no LLM calls)
    document.py            # HeadingEntry, TOCBoundary, DocumentMetadata
    results.py             # ExtractionResult, LogEntry
  pipeline/                # Orchestration and utilities
    extractor.py           # extract_toc() — runs all agents in sequence
    reader.py              # File I/O and content slicing
    heading_map.py         # Nested tree builder
    rule_engine.py         # Rule-based heading classifier
  providers/               # LLM backend abstraction
    factory.py             # build_client() — reads LLM_PROVIDER env var
    anthropic.py           # Anthropic Claude client
    azure.py               # Azure OpenAI wrapper
  cli/
    main.py                # CLI entry point
  __main__.py              # python -m miner_mineru
tests/
  conftest.py              # Shared fixtures (notice_md_path, disco_md_path, bologna_md_path)
  golden/                  # Golden JSON fixtures for integration tests
data/                      # Input documents (one subdir per document)
output/                    # Agent JSON output (gitignored)
.specify/                  # Feature specs (speckit workflow)
```

## Commands

```bash
# Run tests (conda agent env, bypass anyio SSL issue)
PYTHONNOUSERSITE=1 "/c/Users/ERO8OFO/.conda/envs/agent/python.exe" -m pytest -p no:anyio

# Run CLI agent
python -m miner_mineru <markdown_file> --output <output.json>
```

## Code Style

Python 3.11+ (conda `agent` environment): Follow standard conventions

## Recent Changes
- 002-fix-source-markdown: Added Python 3.11+ (conda `agent` environment) + `json` (stdlib), `difflib` (stdlib for fuzzy matching), `os`/`pathlib` (stdlib)

- 002-markdown-summary-extraction: Added Python 3.11+ (conda `agent` environment) + Anthropic Claude API (for LLM-based classification), `json` stdlib

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
