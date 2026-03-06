# Tasks: Markdown Summary & TOC Extraction

**Input**: Design documents from `/specs/002-markdown-summary-extraction/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Included — required by project constitution (Test-First / TDD, pytest, golden tests for 2+ real documents).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [ ] T001 Create `tests/` directory and `tests/golden/` subdirectory per plan.md project structure
- [ ] T002 Create `tests/__init__.py` and `scripts/__init__.py` to make packages importable
- [ ] T003 [P] Create `tests/conftest.py` with shared pytest fixtures: sample markdown file paths for all 3 docs in `data/`
- [ ] T004 [P] Create `requirements.txt` (or add to existing) with `anthropic`, `pytest` dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and TOC boundary detection — must be complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Define `HeadingEntry`, `TOCBoundary`, `DocumentMetadata`, `ExtractionResult`, `LogEntry` dataclasses in `scripts/models.py` per data-model.md
- [ ] T006 [P] Write unit tests for `HeadingEntry` and `ExtractionResult` serialization to/from JSON dict in `tests/test_models.py`
- [ ] T007 Implement `find_toc_boundaries(lines: list[str]) -> TOCBoundary | None` in `scripts/toc_extractor.py` — detects markers `# Summary`, `# TABLE OF CONTENTS`, `# Sommario` (case-insensitive), returns start/end line indices and marker string; returns `None` if not found
- [ ] T008 Write unit tests for `find_toc_boundaries()` in `tests/test_toc_boundary.py` covering: marker present, marker absent, alternate markers (`# Sommario`, `# Summary`), marker at end of file, duplicate markers (use first occurrence)
- [ ] T009 Implement `slice_toc_content(lines: list[str], boundary: TOCBoundary) -> str` in `scripts/toc_extractor.py` — extracts raw text of TOC section from line list
- [ ] T010 Implement `read_markdown_file(path: str) -> list[str]` in `scripts/toc_extractor.py` — reads file, returns lines, raises `FileNotFoundError` on missing file
- [ ] T011 Implement `build_heading_map(flat_entries: list[HeadingEntry]) -> list[HeadingEntry]` in `scripts/toc_extractor.py` — converts flat classified list to nested tree based on `depth` field (section→article→subarticle)

**Checkpoint**: Foundation ready — `toc_extractor.py` library fully tested, models defined. User story phases can now begin.

---

## Phase 3: User Story 1 — Extract TOC from MinerU Markdown (Priority: P1) 🎯 MVP

**Goal**: Given a MinerU markdown file, detect TOC boundaries and classify all entries (section/article/subarticle) with page numbers via LLM. Output structured JSON.

**Independent Test**: `pytest tests/test_toc_extraction.py::test_notice_toc_extraction` passes — TOC boundaries detected and all article entries classified correctly for the Notice of competition sample document.

### Tests for User Story 1

> **Write these tests FIRST — they must FAIL before implementation**

- [ ] T012 [P] [US1] Write golden fixture `tests/golden/notice_toc.json` — manually extract expected TOC entries from `data/Notice_of_competition_.../MinerU_markdown_*.md` (first 15 entries minimum: title, kind, numbering, page)
- [ ] T013 [P] [US1] Write unit test for `classify_toc_entries()` with mocked Claude API response in `tests/test_toc_extraction.py` — verify it returns a list of `HeadingEntry` objects with correct fields
- [ ] T014 [US1] Write golden integration test `test_notice_toc_extraction` in `tests/test_toc_extraction.py` — calls full pipeline on Notice doc, compares `toc` against `tests/golden/notice_toc.json` (title + kind + page must match for 95%+ of entries)

### Implementation for User Story 1

- [ ] T015 [US1] Implement `classify_toc_entries(toc_text: str, client: anthropic.Anthropic) -> list[HeadingEntry]` in `scripts/toc_extractor.py` — sends TOC text to Claude API with structured JSON prompt; LLM classifies each line as `section`/`article`/`subarticle`/`annex`/`topic` with `numbering`, `page`, `depth`, `confidence`; parses JSON response back to `HeadingEntry` list
- [ ] T016 [US1] Implement `extract_toc(file_path: str, client: anthropic.Anthropic) -> ExtractionResult` in `scripts/toc_extractor.py` — orchestrates: `read_markdown_file` → `find_toc_boundaries` → `slice_toc_content` → `classify_toc_entries` → `build_heading_map`; populates `processing_log`; raises `ValueError` (exit code 2) if no TOC found
- [ ] T017 [US1] Implement CLI entry point `scripts/toc_extraction_agent.py` — parses `sys.argv` for `<markdown_file_path>` and optional `--output <path>`; calls `extract_toc()`; writes JSON to file or stdout; handles exit codes 0/1/2/3 per `contracts/cli-contract.md`; logs to stderr

**Checkpoint**: US1 complete — run `python scripts/toc_extraction_agent.py data/Notice_of_competition_.../MinerU_markdown_*.md` and verify JSON output contains correct TOC entries.

---

## Phase 4: User Story 2 — Generate AI-Based Summary (Priority: P2)

**Goal**: Generate a 2-3 sentence summary of the document's purpose and scope using pre-TOC and TOC content.

**Independent Test**: `pytest tests/test_summary.py` passes — summaries for all 3 sample docs are 2-3 sentences and contain document title and at least one major topic.

### Tests for User Story 2

> **Write these tests FIRST — they must FAIL before implementation**

- [ ] T018 [P] [US2] Write unit test for `generate_summary()` with mocked Claude API in `tests/test_summary.py` — verify it returns a non-empty string of 1-3 sentences
- [ ] T019 [US2] Write integration test `test_all_docs_summary` in `tests/test_summary.py` — calls summary generation on all 3 sample docs; asserts each summary is 2-3 sentences; asserts document title appears in summary

### Implementation for User Story 2

- [ ] T020 [US2] Implement `extract_pre_toc_content(lines: list[str], boundary: TOCBoundary) -> str` in `scripts/toc_extractor.py` — returns lines before TOC start (skip image lines `![image](...)`)
- [ ] T021 [US2] Implement `generate_summary(pre_toc_text: str, toc_text: str, client: anthropic.Anthropic) -> str` in `scripts/toc_extractor.py` — sends pre-TOC header + TOC entries to Claude; prompts for 2-3 sentence summary of document purpose and scope
- [ ] T022 [US2] Update `extract_toc()` in `scripts/toc_extractor.py` to call `generate_summary()` and populate `ExtractionResult.summary` field

**Checkpoint**: US2 complete — JSON output now includes a meaningful `summary` field alongside the `toc` and `heading_map`.

---

## Phase 5: User Story 3 — Extract Page Metadata (Priority: P2)

**Goal**: Extract document metadata (title, year, document type, organization) from the document header area and include in JSON output.

**Independent Test**: `pytest tests/test_metadata.py` passes — title and document type correctly identified for all 3 sample docs; year identified where present.

### Tests for User Story 3

> **Write these tests FIRST — they must FAIL before implementation**

- [ ] T023 [P] [US3] Write unit test for `extract_metadata()` with mocked LLM in `tests/test_metadata.py` — verify returns `DocumentMetadata` with at minimum `title` and `source` fields
- [ ] T024 [US3] Write integration test `test_metadata_all_docs` in `tests/test_metadata.py` — calls metadata extraction on all 3 docs; asserts title identified in 100%; asserts year present for docs that have it; asserts `source` is `explicit` or `inferred` as appropriate

### Implementation for User Story 3

- [ ] T025 [US3] Implement `extract_metadata(pre_toc_text: str, client: anthropic.Anthropic) -> DocumentMetadata` in `scripts/toc_extractor.py` — sends document header (pre-TOC lines, max 50 lines) to Claude; prompts for title, year, document_type, organization; marks `source` as `explicit` if found in clear heading, `inferred` if deduced from context
- [ ] T026 [US3] Update `extract_toc()` in `scripts/toc_extractor.py` to call `extract_metadata()` and populate `ExtractionResult.metadata` field

**Checkpoint**: All 3 user stories complete — full `ExtractionResult` JSON with `toc`, `heading_map`, `summary`, `metadata`, `toc_boundaries`, `processing_log`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Golden tests for remaining sample docs, edge cases, and documentation

- [ ] T027 [P] Write golden fixture `tests/golden/disco_toc.json` and add golden test `test_disco_toc_extraction` in `tests/test_toc_extraction.py` for BANDO-DIRITTO sample doc
- [ ] T028 [P] Write golden fixture `tests/golden/bologna_toc.json` and add golden test `test_bologna_toc_extraction` in `tests/test_toc_extraction.py` for bando-di-concorso sample doc (Italian TOC with `# Sommario`)
- [ ] T029 Add edge case tests in `tests/test_toc_boundary.py`: file with no TOC marker (expect exit code 2), empty file, TOC at first line
- [ ] T030 Add LLM API error handling test in `tests/test_toc_extraction.py`: mock API throwing `anthropic.APIError`, verify exit code 3 returned
- [ ] T031 Run `pytest` to confirm all tests pass and success criteria SC-001–SC-007 are met
- [ ] T032 Update `specs/002-markdown-summary-extraction/quickstart.md` with actual commands verified against real documents

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — MVP deliverable, no story dependencies
- **US2 (Phase 4)**: Depends on Phase 2 — can run in parallel with US1 after Phase 2
- **US3 (Phase 5)**: Depends on Phase 2 — can run in parallel with US1/US2 after Phase 2
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: No inter-story dependencies — independently testable
- **US2 (P2)**: Uses `pre_toc_content` from toc_extractor (foundational) — no dependency on US1
- **US3 (P2)**: Uses `pre_toc_content` from toc_extractor (foundational) — no dependency on US1 or US2

### Within Each User Story

- Golden fixture / unit tests written and FAILING first (TDD)
- Models before services (T005 before T015)
- Library functions before CLI wrapper (T016 before T017)
- Integration tests after implementation (T014 after T015–T017)

### Parallel Opportunities

- T003, T004 can run in parallel (Phase 1)
- T006 can run in parallel with T007–T010 (Phase 2, different files)
- T012, T013 can run in parallel (Phase 3 test setup)
- T018, T019 can run in parallel (Phase 4 test setup)
- T023, T024 can run in parallel (Phase 5 test setup)
- T027, T028, T029, T030 can run in parallel (Phase 6)
- US2 (Phase 4) and US3 (Phase 5) can run in parallel after Phase 2

---

## Parallel Example: User Story 1

```bash
# Run in parallel — write golden fixture and unit test simultaneously:
Task T012: "Write golden fixture tests/golden/notice_toc.json"
Task T013: "Write unit test for classify_toc_entries() with mock in tests/test_toc_extraction.py"

# Then sequentially:
Task T014: Integration test (depends on T012 golden fixture)
Task T015: Implement classify_toc_entries()
Task T016: Implement extract_toc() (depends on T015)
Task T017: Implement CLI entry point (depends on T016)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (models + boundary detection)
3. Complete Phase 3: US1 — TOC extraction + LLM classification + CLI
4. **STOP and VALIDATE**: `python scripts/toc_extraction_agent.py data/Notice.../MinerU_*.md`
5. Demo: JSON with `toc`, `heading_map`, `toc_boundaries`, `processing_log`

### Incremental Delivery

1. Phase 1 + 2 → Foundation
2. Phase 3 (US1) → MVP: TOC extracted, classified, heading map built
3. Phase 4 (US2) → Add `summary` to output
4. Phase 5 (US3) → Add `metadata` to output
5. Phase 6 → All 3 golden tests pass, edge cases handled

---

## Notes

- `[P]` tasks operate on different files and have no dependencies — safe to run in parallel
- `[US1/US2/US3]` label maps each task to its user story for traceability
- Tests MUST fail before implementation (TDD per constitution)
- The `classify_toc_entries()` function is the only LLM-dependent function — all others are deterministic and independently testable without API calls
- LLM classification uses `claude-haiku-4-5` (fast, cost-effective per research.md Decision 1)
- `ANTHROPIC_API_KEY` environment variable must be set for LLM tasks (T015, T021, T025)
- Commit after each phase checkpoint
