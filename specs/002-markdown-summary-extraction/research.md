# Research: Markdown Summary & TOC Extraction

## Decision 1: LLM API for Classification

**Decision**: Use Anthropic Claude API (claude-haiku-4-5 or claude-sonnet-4-5) for TOC entry classification.

**Rationale**: The project already uses Claude tooling. Haiku is fast and cheap for structured extraction tasks. The agent reads the TOC text block and classifies each entry as section/article/subarticle with page number — a well-scoped task for an LLM.

**Alternatives considered**:
- OpenAI GPT-4o: viable but project is already in the Anthropic ecosystem
- Local LLM (Ollama): adds deployment complexity, slower for this use case
- Regex rules (feature-001 approach): explicitly rejected by user — agent-based classification preferred

## Decision 2: TOC Boundary Detection Strategy

**Decision**: Simple string matching for TOC markers (`# Summary`, `# TABLE OF CONTENTS`, `# Sommario`), then LLM classifies content within boundaries.

**Rationale**: MinerU output uses consistent markdown heading markers for TOC sections. Finding the marker is deterministic and doesn't need an LLM. The boundary ends when the next `#` heading at same or higher level appears that is clearly not a TOC entry (i.e., the start of document body content). The LLM handles the nuanced part: classifying what's inside.

**Alternatives considered**:
- Full LLM scan of entire document: wasteful, slow, expensive
- Line-count heuristic: fragile, varies by document length
- Regex-only for everything: rejected per clarification — LLM decides classification

## Decision 3: Output JSON Schema

**Decision**: Single JSON file per document with keys: `toc`, `summary`, `metadata`, `toc_boundaries`, `heading_map`, `processing_log`, `extracted_at`.

**Rationale**: Flat JSON file is easy to consume by downstream agents and test against golden outputs. The `heading_map` is the key deliverable — a tree structure the rewriting agent needs.

**Alternatives considered**:
- Multiple output files (separate TOC, metadata, summary): adds complexity with no clear benefit
- YAML output: JSON is constitution-mandated for interchange
- Database storage: overkill for offline batch processing

## Decision 4: Agent Architecture

**Decision**: Two-function design: (1) `find_toc_boundaries()` — deterministic, reads file, finds TOC markers, returns line ranges. (2) `classify_toc_entries()` — sends TOC text to LLM with structured prompt, gets back classified entries.

**Rationale**: Separates deterministic I/O from LLM classification. The boundary finder is testable without API calls. The classifier is testable with mocked LLM responses. Aligns with Library-First constitution principle.

**Alternatives considered**:
- Single monolithic function: harder to test, violates Library-First
- Multi-agent orchestration: over-engineered for this scope
- Streaming classification (entry-by-entry): slower, more API calls, no benefit since TOC fits in one prompt

## Decision 5: Prompt Strategy for Classification

**Decision**: Send the entire TOC text block to the LLM in a single call with a structured output prompt. The prompt instructs the LLM to return a JSON array where each entry has `title`, `kind` (section/article/subarticle), `numbering`, `page`, `depth`.

**Rationale**: TOC sections in legal documents are typically 20-80 entries — well within a single prompt. Structured output (JSON mode) ensures parseable results. One call per document keeps cost and latency minimal.

**Alternatives considered**:
- Few-shot prompting with examples from each document: adds maintenance burden; the LLM can handle this zero-shot given clear instructions
- Tool-use / function-calling: unnecessary overhead for a single structured extraction
- Chain-of-thought + classification: slower, no accuracy benefit for this structured task
