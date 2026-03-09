# MinerU JSON Loader Guide

## Overview

The JSON loader cleans and processes raw MinerU JSON extraction files, removing unnecessary spatial metadata and producing a minimal, clean JSON output with only essential fields.

## Quick Start

### CLI Usage

```bash
# Load and clean MinerU JSON
python -m miner_mineru load <json_file> --output <output.json>

# Example
python -m miner_mineru load data/MinerU_*.json -o output/cleaned.json
```

### Python API

```python
from miner_mineru import load_mineru_json, save_cleaned_json

# Load MinerU JSON
doc = load_mineru_json('data/MinerU_document.json')

# Save cleaned JSON
save_cleaned_json(doc, 'output/cleaned.json')

# Access blocks
for block in doc.get_all_blocks():
    print(f"{block.type.value}: {block.content}")
```

## What Gets Removed

The loader removes these unnecessary keys:

| Key | Why Removed |
|-----|------------|
| `bbox` | Spatial bounding box (not needed for text processing) |
| `angle` | Text rotation angle |
| `index` | Original block index from extraction |
| `lines` | Raw nested structure (aggregated into `content`) |
| `spans` | Raw text spans (aggregated into `content`) |
| `detected_role` | Internal classification metadata |
| `has_ocr_issues` | Processing flag |
| `normalized_reading_order` | Internal ordering metadata |
| `source_spans_count` | Internal count metadata |

## What Gets Kept

### All Blocks
- **`type`** — Block type: `title`, `text`, `list`, `table`, `equation`
- **`content`** — Aggregated text content (optional, for title/text blocks)

### List Blocks
- **`list`** — Array of list items with structure:
  ```json
  {
    "index": 0,
    "content": "List item text"
  }
  ```

### Table Blocks
- **`table`** — Table structure with HTML content:
  ```json
  {
    "html": "<table>...</table>"
  }
  ```

## Output Structure

```json
{
  "metadata": {
    "source_file": "path/to/MinerU_file.json",
    "total_pages": 24,
    "total_blocks": 269
  },
  "blocks": [
    {
      "type": "title",
      "content": "Document Title"
    },
    {
      "type": "text",
      "content": "Body text paragraph..."
    },
    {
      "type": "list",
      "list": [
        {"index": 0, "content": "Item 1"},
        {"index": 1, "content": "Item 2"}
      ]
    },
    {
      "type": "table",
      "table": {
        "html": "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>"
      }
    }
  ]
}
```

## File Size Reduction

The loader significantly reduces file size by removing unnecessary keys:

| Metric | Example |
|--------|---------|
| Original | 1.5 MB |
| Cleaned | 120 KB |
| Reduction | 8x smaller |

## Block Types

| Type | Usage |
|------|-------|
| `title` | Document headings and section titles |
| `text` | Body text and paragraphs |
| `list` | Enumerated or bulleted lists |
| `table` | Tables (stored as HTML) |
| `equation` | Mathematical equations |
| `unknown` | Unclassified blocks |

## Python API Reference

### `load_mineru_json(json_path: str) -> Document`

Load and clean a MinerU JSON extraction file.

**Arguments:**
- `json_path` — Path to MinerU JSON file

**Returns:**
- `Document` — Cleaned document with blocks

**Raises:**
- `FileNotFoundError` — If JSON file not found
- `json.JSONDecodeError` — If JSON is invalid
- `ValueError` — If JSON structure is unexpected

**Example:**
```python
doc = load_mineru_json('data/MinerU_file.json')
print(f"Pages: {doc.total_pages}, Blocks: {len(doc.get_all_blocks())}")
```

### `save_cleaned_json(doc: Document, output_path: str) -> None`

Save cleaned document to JSON file.

**Arguments:**
- `doc` — Document object to save
- `output_path` — Output JSON file path

**Example:**
```python
save_cleaned_json(doc, 'output/cleaned.json')
```

### `Document` Class

The `Document` class represents a cleaned extraction result.

**Attributes:**
- `source_file` — Path to source JSON
- `pages` — List of `Page` objects
- `total_pages` — Number of pages
- `metadata` — Document metadata dict

**Methods:**
- `get_all_blocks() -> List[Block]` — Get all blocks from all pages
- `to_dict() -> Dict` — Export to dictionary (for JSON serialization)

### `Page` Class

Single page with extracted blocks.

**Attributes:**
- `page_idx` — Page number (0-indexed)
- `blocks` — List of `Block` objects
- `page_width` — Page width in points
- `page_height` — Page height in points

### `Block` Class

Single extracted block.

**Attributes:**
- `block_id` — Unique block identifier
- `page_idx` — Page number
- `type` — `BlockType` enum (title, text, list, table, equation)
- `content` — Text content (optional)
- `confidence` — OCR confidence score (optional, 0-1)
- `list_items` — List items array (if type is list)
- `table` — Table structure (if type is table)

**Methods:**
- `to_dict() -> Dict` — Export to dictionary (minimal keys only)

## Integration with Pipeline

The JSON loader is the first step in the JSON-based processing pipeline:

```
MinerU JSON (raw)
    ↓
  load_mineru_json() — Remove spatial keys, aggregate text
    ↓
Cleaned JSON
    ↓
[Future: Process with agents for TOC extraction, entity recognition, etc.]
```

## Error Handling

```python
from miner_mineru import load_mineru_json

try:
    doc = load_mineru_json('data/file.json')
except FileNotFoundError:
    print("File not found")
except json.JSONDecodeError:
    print("Invalid JSON")
except ValueError as e:
    print(f"Invalid structure: {e}")
```

## Performance

- **Time:** ~0.5s for 1.5MB JSON with 269 blocks
- **Memory:** Minimal overhead (blocks are streamed)
- **Output:** 8x smaller than input

## See Also

- [Quick Start Guide](QUICK_START.md) — Get started with the full pipeline
- [Batch Pipeline](BATCH_PIPELINE.md) — Process multiple documents
