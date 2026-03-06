# Feature Specification: Markdown Summary & Table of Contents Extraction

**Feature Branch**: `002-markdown-summary-extraction`
**Created**: 2026-03-06
**Status**: Draft
**Input**: User description: "Find summary or table of contents from first pages of markdown files"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Extract TOC from MinerU Markdown (Priority: P1)

A user provides a MinerU-generated markdown file and needs to automatically detect the TOC/Summary section, extract all article entries with page numbers, and produce a structured heading map so that downstream agents can rewrite headings with proper hierarchy.

**Why this priority**: This is the primary value—detecting the TOC boundary and extracting article/section/subarticle structure is the foundation for all downstream processing (heading rewriting, navigation, search).

**Independent Test**: Run the extraction on a sample MinerU markdown file and validate that the TOC boundaries are correctly detected and all article entries with page numbers match the source document's table of contents.

**Acceptance Scenarios**:

1. **Given** a MinerU markdown with `# TABLE OF CONTENTS` section listing articles with page numbers, **When** extraction runs, **Then** the TOC start/end boundaries are identified and all entries are parsed into a structured hierarchy (section → article → subarticle) with page numbers.
2. **Given** a MinerU markdown with `# Summary` or `# Sommario` as the TOC marker, **When** extraction runs, **Then** the alternate marker is recognized and parsed identically.
3. **Given** a MinerU markdown with mixed content before the TOC (images, disclaimers, update notices), **When** extraction runs, **Then** only the TOC section is extracted, pre-TOC content is skipped.

---

### User Story 2 - Generate AI-Based Summary (Priority: P2)

A user needs an AI-generated summary of the document's purpose, scope, and key sections from the content before and around the TOC to quickly understand what the document covers without extensive manual reading.

**Why this priority**: Summaries provide business context and help users decide if they need to read the full document, reducing cognitive load.

**Independent Test**: Generate summaries for the 3 sample MinerU markdown documents and validate that summaries accurately capture document scope and primary topics.

**Acceptance Scenarios**:

1. **Given** a MinerU markdown file with title and introductory sections before the TOC, **When** summary is generated, **Then** summary includes document title, purpose statement, and list of major topics in 2-3 sentences.
2. **Given** a legal document with formal structure, **When** summary is generated, **Then** key entities (articles, sections, requirements) are identified and included in summary.

---

### User Story 3 - Extract Page Metadata (Priority: P2)

Users need metadata about the document (title, date, authors, page count) extracted automatically from the document header area to populate document index and enable filtering.

**Why this priority**: Metadata enables cataloging and discovery of documents without manual data entry.

**Independent Test**: Extract metadata from MinerU markdown files and verify that recognized fields (title, date, author) are correctly identified and extracted.

**Acceptance Scenarios**:

1. **Given** a MinerU markdown file with title heading and academic year reference, **When** extraction runs, **Then** metadata fields (title, year, document type) are parsed and returned as structured data.
2. **Given** a MinerU markdown file without explicit metadata fields, **When** extraction runs, **Then** system infers metadata from content (e.g., first heading as title) and marks inferred vs. explicit.

### Edge Cases

- What happens when MinerU markdown file has no TOC/Summary section at all?
- How does system handle extremely large files (agent scans for TOC markers, does not read entire file into memory)?
- What happens when TOC entries have inconsistent formatting (missing page numbers, mixed numbering styles)?
- How does system handle markdown without metadata or clear purpose statement?
- What happens when TOC markers appear multiple times (e.g., duplicate `# Summary` headings)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Agent MUST accept a MinerU-generated markdown file path and detect and parse the TOC/Summary section boundaries. Input is limited to MinerU PDF-extraction output with known patterns (`# Summary`, `# TABLE OF CONTENTS`, `# Sommario`, numbered article listings with page numbers).
- **FR-002**: Agent MUST extract heading hierarchy from the TOC section using LLM-based classification (no hardcoded regex). The agent reads each TOC entry and semantically decides its kind (section, article, subarticle), returning a structured tree with heading level, text, page number, and nesting relationships.
- **FR-003**: Agent MUST identify and parse explicit table of contents sections using known MinerU TOC markers (`# Summary`, `# TABLE OF CONTENTS`, `# Sommario`).
- **FR-004**: Agent MUST extract document metadata from the document header area: title (first major heading), academic year/date, document type, issuing organization.
- **FR-005**: Agent MUST generate a 2-3 sentence AI-based summary of document purpose and scope using pre-TOC and TOC content.
- **FR-006**: Agent MUST return outputs in structured JSON format with keys: `toc`, `summary`, `metadata`, `toc_boundaries`, `extracted_at`.
- **FR-007**: Agent MUST handle edge cases: missing TOC section, inconsistent entry formatting, malformed numbering, and document structure variations.
- **FR-008**: Agent SHOULD produce consistent outputs for the same input. Since classification is LLM-based, minor variation is acceptable but the heading hierarchy structure (section → article → subarticle mapping) MUST remain stable across runs.
- **FR-009**: Agent MUST provide confidence scores or source indicators for extracted elements (e.g., inferred vs. explicit metadata).
- **FR-010**: Agent MUST log processing decisions and any skipped content for auditability.
- **FR-011**: Agent output MUST include TOC boundary positions (start/end line numbers) so downstream agents can locate the TOC section in the source file.
- **FR-012**: Agent output MUST provide a structured heading map (section → article → subarticle hierarchy with page numbers) suitable for a downstream agent to rewrite markdown headings with proper depth (`# Section`, `## Article`, `### Subarticle`).

### Key Entities

- **MarkdownDocument**: MinerU-generated markdown file with content, structure, and TOC section.
- **TOCBoundary**: Start and end line numbers of the detected TOC/Summary section.
- **HeadingEntry**: A single TOC entry with title, numbering, page number, and depth level.
- **HeadingHierarchy**: Extracted heading tree with section → article → subarticle nesting relationships.
- **DocumentMetadata**: Title, date/year, document type, issuing organization, extracted from document header.
- **ExtractionResult**: Complete output containing TOC, hierarchy, summary, metadata, boundaries, and processing log.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agent correctly detects TOC section boundaries in 100% of the 3 sample MinerU documents.
- **SC-002**: Agent extracts TOC entries with 95%+ accuracy (correct title, numbering, page number) across all sample documents.
- **SC-003**: Extracted headings preserve correct nesting depth (section → article → subarticle) in 98%+ of entries.
- **SC-004**: Summaries generated are 2-3 sentences and accurately describe document scope without hallucination or false details.
- **SC-005**: Metadata extraction identifies title and document type in 100% of sample documents; date/year when present.
- **SC-006**: Processing time per document completes in under 5 seconds.
- **SC-007**: Heading map output is directly consumable by a downstream heading-rewriting agent without manual intervention.

## Assumptions

- Input files are MinerU-generated markdown from PDF extraction, with predictable structure (headings, TOC sections, article numbering patterns).
- TOC section boundaries are detectable via known markers (`# Summary`, `# TABLE OF CONTENTS`, `# Sommario`) in MinerU output.
- AI-based summary generation uses available Claude API (or equivalent LLM) for semantic understanding.
- TOC entries follow patterns like `Art. N Title PageNum`, `N.N.N Title PageNum`, or `SECTION TITLE PageNum`.
- Users prioritize completeness and accuracy over execution speed for this offline processing task.
- This agent is stage 1 of a two-stage pipeline; stage 2 (heading rewriting) is a separate feature.

## Notes

- This feature replaces the regex-based heading-extraction pipeline (feature-001) with an LLM agent-based approach.
- Designed as first stage of a two-stage pipeline: (1) TOC extraction (this feature), (2) heading rewriting by a downstream preprocessing agent.

## Clarifications

### Session 2026-03-06
- Q: Input source scope — MinerU-only or any markdown? → A: Option A — MinerU-generated markdown only; leverage known patterns (`# Summary`, `# TABLE OF CONTENTS`, numbered article lines with page numbers).
- Q: How should the agent determine scanning boundary? → A: TOC-section detection — find the TOC start marker, scan until the TOC section ends, extract all article entries with page numbers. No line-count or page-break heuristic needed.
- Q: What happens after TOC extraction? → A: Two-stage pipeline: (1) This agent extracts TOC boundaries, article entries, and page numbers as structured data. (2) A downstream preprocessing agent uses that TOC map to rewrite headings in the markdown with proper hierarchy (`# Section`, `## Article`, `### Subarticle`).

- Q: How should the agent determine heading depth/hierarchy from TOC entries? → A: Option A depth mapping (Section → 1, Article → 2, Subarticle → 3+), but classification MUST be performed by the LLM agent — no hardcoded regex. The agent reads each TOC entry and decides its kind (section, article, subarticle) based on semantic understanding of the content.
- Q: Relationship to feature-001 (heading-extraction)? → A: Replace entirely. The LLM agent-based TOC extraction supersedes the regex rule engine from feature-001. One agent finds the TOC, classifies entries (section, article, subarticle) with page numbers, and stores the result as JSON.

**End of spec**
