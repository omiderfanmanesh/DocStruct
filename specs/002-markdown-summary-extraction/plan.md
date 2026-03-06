# Implementation Plan: Markdown Summary & TOC Extraction

**Branch**: `002-markdown-summary-extraction` | **Date**: 2026-03-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-markdown-summary-extraction/spec.md`

## Summary

Build an LLM agent that reads MinerU-generated markdown files, detects the TOC/Summary section boundaries, extracts all heading entries (section, article, subarticle) with page numbers using semantic classification (no regex), and outputs a structured JSON file. This replaces the regex-based heading-extraction pipeline (feature-001). A downstream agent will consume the JSON to rewrite markdown headings with proper depth hierarchy.

## Technical Context

**Language/Version**: Python 3.11+ (conda `agent` environment)
**Primary Dependencies**: Anthropic Claude API (for LLM-based classification), `json` stdlib
**Storage**: JSON file output (`toc_extraction.json`)
**Testing**: pytest
**Target Platform**: Windows 11 (local CLI tool)
**Project Type**: CLI tool / library
**Performance Goals**: <5 seconds per document
**Constraints**: MinerU-generated markdown only; no regex for classification; LLM decides heading kinds
**Scale/Scope**: 3 sample documents initially; designed to work on any MinerU PDF-extracted markdown

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | ✅ Pass | TOC extraction logic will be a reusable module with clear public API |
| CLI-First Interfaces | ✅ Pass | CLI entry point accepting file path, outputting JSON to stdout/file |
| Test-First (TDD) | ✅ Pass | Golden tests against 3 sample documents; unit tests for TOC boundary detection |
| Integration & Contract Testing | ✅ Pass | Contract defined for JSON output schema; integration test with real MinerU files |
| Observability, Versioning & Simplicity | ✅ Pass | Structured logging of classification decisions; JSON output includes processing log |

**Gate result: PASS** — No violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/002-markdown-summary-extraction/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
scripts/
├── toc_extraction_agent.py   # Main agent: reads markdown, calls LLM, outputs JSON
├── toc_extractor.py          # Library: TOC boundary detection, content slicing
└── structure_pipeline.py     # Existing (to be replaced)

tests/
├── test_toc_extraction.py    # Golden tests against 3 sample docs
├── test_toc_boundary.py      # Unit tests for TOC marker detection
└── golden/                   # Expected JSON outputs for each sample doc
    ├── notice_toc.json
    ├── disco_toc.json
    └── bologna_toc.json

data/
├── Notice_of_competition.../MinerU_markdown_*.md   # Sample 1
├── BANDO-DIRITTO.../MinerU_markdown_*.md           # Sample 2
└── bando-di-concorso.../MinerU_markdown_*.md       # Sample 3
```

**Structure Decision**: Single project layout. `scripts/` for CLI entry points, `tests/` for all test levels. The agent script calls the Claude API and writes JSON output. The library module handles file I/O and TOC boundary detection (deterministic, no LLM needed for finding markers).

## Complexity Tracking

No constitution violations — table not needed.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | ✅ Pass | `toc_extractor.py` is a reusable library; `toc_extraction_agent.py` is the CLI wrapper |
| CLI-First Interfaces | ✅ Pass | CLI contract defined in `contracts/cli-contract.md`; JSON output to stdout or file |
| Test-First (TDD) | ✅ Pass | Golden tests for 3 docs + unit tests for boundary detection planned |
| Integration & Contract Testing | ✅ Pass | JSON schema contract defined in data-model.md; CLI contract with exit codes |
| Observability, Versioning & Simplicity | ✅ Pass | `processing_log` in output JSON; structured stderr logging; simple 2-function design |

**Post-design gate: PASS**
