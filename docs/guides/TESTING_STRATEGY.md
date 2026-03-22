# Testing Strategy

## Goals

- Verify each pipeline stage independently.
- Catch schema drift from LLM responses before it breaks downstream stages.
- Keep a fast local loop for refactors and a smaller set of live end-to-end checks for provider integration.

## Pipeline Stages To Test

1. Input and file I/O
2. TOC boundary detection
3. TOC entry extraction and normalization
4. Heading tree construction
5. Summary generation
6. Metadata extraction
7. TOC-to-source matching
8. Heading correction and report generation
9. CLI entrypoints
10. Batch runner scripts

## Test Pyramid

### Unit Tests

Use mocks for the LLM port and cover deterministic logic only.

- `domain.heading_classifier`
  - rule matching by heading kind
  - decimal numbering behavior
  - unknown fallback behavior
- `domain.heading_matcher`
  - exact match
  - embedded match and line splitting
  - TOC-section skipping
  - LLM candidate collection
- `domain.level_mapper`
  - kind-to-level mapping
  - doc-title promotion
  - demotion of unmatched headings
- `infrastructure.file_io`
  - markdown read/write
  - report serialization
- `application.agents.boundary_agent`
  - normal JSON dict entries
  - stringified JSON entries
  - plain string entries
  - chunk rollover across multiple calls
- `application.agents.summary_agent`
  - prompt assembly
  - one-call behavior
- `application.agents.metadata_agent`
  - JSON parsing
  - fenced-response stripping
- `application.agents.llm_heading_matcher`
  - response parsing
  - no-match handling

### Contract Tests

These protect the assumptions between stages.

- `extract_toc()` returns:
  - `toc`
  - `heading_map`
  - `summary`
  - `metadata`
  - `toc_boundaries`
  - `processing_log`
  - `extracted_at`
- `fix_markdown()` returns a valid `CorrectionReport`
- CLI exit codes remain stable:
  - `extract`: `0`, `1`, `2`, `3`
  - `fix`: `0`, `1`
- LLM adapters always return plain text from `create_message()`

### Integration Tests

Run the real orchestration with mocked LLM responses.

- `extract_toc()` against golden fixtures
- `fix_markdown()` against sample markdown + TOC JSON
- extraction handling messy boundary-agent payloads
- LLM fallback matching for noisy source lines
- corrected markdown preserves non-heading content verbatim

### CLI Tests

Run subprocess-style tests for:

- `python -m docstruct`
- `python -m docstruct extract ...`
- `python -m docstruct fix ...`
- output file creation
- stderr progress messages
- exit code handling

### Batch Script Smoke Tests

Use a temporary directory with one synthetic markdown file and mocked extraction JSON.

- `tools/run_pipeline.py`
- `tools/run_fixer.py`
- `tools/run_pipeline_all.py --skip-extract`

## Live Provider Checks

Run these sparingly because they consume API quota.

### Extraction Smoke Check

```powershell
python -m docstruct extract .\data\<file>.md --output .\output\smoke.json
```

Verify:

- TOC JSON is created
- boundary lines look plausible
- `toc` is non-empty
- `metadata.title` is populated

### Full Pipeline Smoke Check

```powershell
python .\tools\run_pipeline.py .\data\<file>.md
```

Verify:

- extraction step succeeds
- fix step succeeds
- corrected markdown is written
- report JSON is written
- unmatched TOC entries are within an acceptable range

## Recommended Local Workflow

### Fast Loop

```powershell
python -m pytest tests\test_toc_boundary.py tests\test_toc_extraction.py tests\test_md_fixer.py -q
```

### Full Regression

```powershell
python -m pytest -q -p no:anyio
```

### Before Shipping Refactors

1. Run full regression suite.
2. Run one live extraction smoke check.
3. Run one live full-pipeline smoke check.
4. Inspect generated markdown and report manually for at least one real document.

## Failure Triage Guide

- Boundary agent crashes:
  - inspect raw `entries` shape first
  - check fenced JSON and stringified entry objects
- Extraction succeeds but TOC quality is poor:
  - inspect boundary range
  - inspect `toc` kind/depth distribution
- Fixer under-corrects:
  - inspect `pattern`, `numbering`, and `separator` in extracted TOC
  - inspect unmatched entries in the report
- CLI works but scripts fail:
  - check `PYTHONPATH` handling in `tools/`
  - check file paths and output directory creation
