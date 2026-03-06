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

### User Story 1 - Extract TOC from Markdown (Priority: P1)

A user provides a markdown file and needs to automatically extract the table of contents from the first pages so they can quickly understand document structure and navigate to relevant sections without reading the entire file.

**Why this priority**: This is the primary value—users can quickly scan document organization and jump to sections of interest, enabling faster document consumption.

**Independent Test**: Run the extraction on a sample markdown file and validate that the extracted TOC contains correct heading hierarchy and matches visible structure from first 5 pages.

**Acceptance Scenarios**:

1. **Given** a markdown file with heading hierarchy (H1, H2, H3), **When** extraction runs on the first 5 pages, **Then** all headings are extracted with correct nesting depth preserved and returned as a structured outline.
2. **Given** a markdown file with table of contents section already present, **When** extraction runs, **Then** the explicit TOC is identified and returned with heading-to-content mappings.
3. **Given** a markdown file with mixed content (text, code blocks, tables), **When** extraction runs on first pages, **Then** only headings are extracted, non-heading content is filtered out.

---

### User Story 2 - Generate AI-Based Summary (Priority: P2)

A user needs an AI-generated summary of the document's purpose, scope, and key sections from the first pages to quickly understand what the document covers without extensive manual reading.

**Why this priority**: Summaries provide business context and help users decide if they need to read the full document, reducing cognitive load.

**Independent Test**: Generate summaries for 5 different markdown documents and validate that summaries accurately capture document scope and primary topics mentioned in first pages.

**Acceptance Scenarios**:

1. **Given** a markdown file with introduction and opening sections, **When** summary is generated, **Then** summary includes document title, purpose statement, and list of major topics in 2-3 sentences.
2. **Given** a legal or technical document with formal structure, **When** summary is generated, **Then** key entities (articles, sections, requirements) are identified and included in summary.

---

### User Story 3 - Extract Page Metadata (Priority: P2)

Users need metadata about the document (title, date, authors, page count) extracted automatically from first pages to populate document index and enable filtering.

**Why this priority**: Metadata enables cataloging and discovery of documents without manual data entry.

**Independent Test**: Extract metadata from markdown files and verify that recognized fields (title, date, author) are correctly identified and extracted.

**Acceptance Scenarios**:

1. **Given** a markdown file with YAML front matter or metadata section, **When** extraction runs, **Then** metadata fields are parsed and returned as structured data.
2. **Given** a markdown file without explicit metadata, **When** extraction runs, **Then** system infers metadata from content (e.g., first heading as title) and marks inferred vs. explicit.

### Edge Cases

- What happens when markdown file has no clear heading structure (all paragraph text)?
- How does system handle extremely large files (limit scanning to first N pages)?
- What happens when headings are malformed or inconsistent in nesting (e.g., H1 → H3 skip)?
- How does system handle markdown without metadata or clear purpose statement?
- Should code blocks and tables in first pages be included in summary context?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: Agent MUST accept a markdown file path and process only the first N pages (configurable, default 5 pages).
- **FR-002**: Agent MUST extract heading hierarchy from markdown and return structured tree with heading level, text, and nesting relationships.
- **FR-003**: Agent MUST identify and parse explicit table of contents sections if present in the document.
- **FR-004**: Agent MUST extract document metadata from common locations: YAML front matter, first section heading, introductory paragraphs (title, date, author, document type).
- **FR-005**: Agent MUST generate a 2-3 sentence AI-based summary of document purpose and scope using first-page content.
- **FR-006**: Agent MUST return outputs in structured JSON format with keys: `toc`, `summary`, `metadata`, `extracted_at`.
- **FR-007**: Agent MUST handle edge cases: missing headings, inconsistent nesting, malformed markdown, and document structure variations.
- **FR-008**: Agent MUST be deterministic and idempotent: same input file produces same output regardless of processing order.
- **FR-009**: Agent MUST provide confidence scores or source indicators for extracted elements (e.g., inferred vs. explicit metadata).
- **FR-010**: Agent MUST log processing decisions and any skipped content for auditability.

### Key Entities

- **MarkdownDocument**: Input file with content, structure, and optional metadata.
- **HeadingHierarchy**: Extracted heading tree with levels, text, and nesting relationships.
- **TableOfContents**: Structured list of sections with page numbers (if available) and heading references.
- **DocumentMetadata**: Title, author, date, document type, extracted from content or front matter.
- **ExtractionResult**: Complete output containing TOC, summary, metadata, and processing metadata.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: Agent extracts TOC from markdown files with 95%+ accuracy on test set of 10 diverse legal/technical documents.
- **SC-002**: Extracted headings preserve correct nesting depth (no level skips that don't match source markdown) in 98%+ of cases.
- **SC-003**: Summaries generated are 2-3 sentences and accurately describe document scope without hallucination or false details.
- **SC-004**: Metadata extraction identifies title in 90%+ of documents tested; date and author when explicitly present in 85%+ of cases.
- **SC-005**: Processing time for average markdown document (50-100 pages) completes in under 5 seconds.
- **SC-006**: Agent successfully processes markdown files of varying formats (YAML front matter, APA, legal documents, technical specs) with consistent output structure.

## Assumptions

- Input markdown files are well-formed (valid markdown syntax).
- First N pages can be determined by counting line breaks or implementing a reasonable page break heuristic.
- AI-based summary generation uses available Claude API (or equivalent LLM) for semantic understanding.
- Metadata may be in multiple formats (YAML, HTML comments, narrative text) and system attempts reasonable extraction.
- Users prioritize completeness and accuracy over execution speed for this offline processing task.

## Notes

- This feature complements the existing heading-extraction pipeline by providing a higher-level content discovery tool.
- Reusable for any markdown document type: legal notices, technical documentation, research papers, etc.

**End of spec**
