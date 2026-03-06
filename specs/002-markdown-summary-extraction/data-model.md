# Data Model: Markdown Summary & TOC Extraction

## Entities

### HeadingEntry

A single classified TOC entry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | yes | Heading text (e.g., "General principles") |
| kind | enum | yes | One of: `section`, `article`, `subarticle`, `annex`, `topic` |
| numbering | string | no | Original numbering (e.g., "Art. 1", "2.1.3", "SECTION I") |
| page | int | no | Page number from TOC entry |
| depth | int | yes | Hierarchy depth: section=1, article=2, subarticle=3+ |
| children | HeadingEntry[] | no | Nested child entries |
| confidence | float | no | LLM confidence score (0.0-1.0) |

### TOCBoundary

Location of TOC section in the source file.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| start_line | int | yes | First line of TOC section (0-indexed) |
| end_line | int | yes | Last line of TOC section (0-indexed) |
| marker | string | yes | The TOC marker found (e.g., "# TABLE OF CONTENTS") |

### DocumentMetadata

Extracted metadata from document header.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | yes | Document title |
| year | string | no | Academic year or date (e.g., "2025/26") |
| document_type | string | no | Type of document (e.g., "Notice of competition", "Call for applications") |
| organization | string | no | Issuing organization |
| source | enum | yes | One of: `explicit` (from heading/front matter), `inferred` (from content) |

### ExtractionResult

Complete output of the TOC extraction agent.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| toc | HeadingEntry[] | yes | Flat list of all TOC entries with classification |
| heading_map | HeadingEntry[] | yes | Hierarchical tree (entries with children nested) |
| summary | string | yes | 2-3 sentence AI-generated summary |
| metadata | DocumentMetadata | yes | Extracted document metadata |
| toc_boundaries | TOCBoundary | yes | Line positions of TOC section |
| processing_log | LogEntry[] | yes | Classification decisions and skipped content |
| extracted_at | string | yes | ISO 8601 timestamp |

### LogEntry

Audit log entry for a processing decision.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| line | int | no | Source line number |
| action | string | yes | What was done (e.g., "classified", "skipped", "inferred") |
| detail | string | yes | Explanation |

## Relationships

```
ExtractionResult
├── toc: HeadingEntry[] (flat)
├── heading_map: HeadingEntry[] (tree)
│   └── children: HeadingEntry[] (recursive)
├── metadata: DocumentMetadata
├── toc_boundaries: TOCBoundary
└── processing_log: LogEntry[]
```

## State Transitions

Not applicable — this is a stateless extraction pipeline. Input file → single JSON output. No lifecycle or state management needed.
