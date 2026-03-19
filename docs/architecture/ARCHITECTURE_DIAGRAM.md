# Enhanced Pipeline Architecture

## Current Architecture (Feature 002)

```
┌─────────────┐
│ source.md   │
│ (markdown)  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│   Current Pipeline       │
│   extract titles from    │
│   markdown using regex   │
└──────┬───────────────────┘
       │
       ▼
┌─────────────────────────┐
│ Extracted Titles        │
│ (from markdown)         │
└──────┬──────────────────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌─────────────────┐   ┌──────────────┐
│ Match against   │   │ toc.json     │
│ TOC             │   │ (TOC entries)│
└──────┬──────────┘   └──────────────┘
       │
       ▼
┌──────────────────────────┐
│ Apply corrections        │
│ (fix heading levels)     │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ fixed_markdown.md        │
│ fixed_report.json        │
└──────────────────────────┘

⚠️  PROBLEMS:
- Working with corrupted text (markdown is re-OCR'd)
- Can't detect footers (no spatial info)
- No quality metrics
- Limited to markdown accuracy
```

## Enhanced Architecture (Feature 003 - Proposed)

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT SOURCES                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  source.md          toc.json         pdf_data.json     │
│  (markdown)         (TOC entries)    (original JSON)    │
│                                                         │
└──────┬────────────────────┬──────────────┬──────────────┘
       │                    │              │
       │ (optional)         │              │ (new)
       │                    │              │
       ▼                    ▼              ▼
┌────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ Markdown       │  │ TOC Data     │  │ JSON Parser          │
│ (ignored if    │  │ ├─entries    │  │ ├─extract text       │
│  JSON avail)   │  │ ├─kind       │  │ ├─get confidence     │
│                │  │ └─numbering  │  │ ├─detect footers     │
└────────────────┘  └──────────────┘  │ └─sort by position   │
                                       └──────┬───────────────┘
                                              │
                                              ▼
                                    ┌──────────────────────┐
                                    │ Cleaned Blocks       │
                                    │ ├─type               │
                                    │ ├─content (from JSON)│
                                    │ ├─page               │
                                    │ ├─y_position         │
                                    │ ├─ocr_score          │
                                    │ ├─is_footer          │
                                    │ └─bbox               │
                                    └──────┬───────────────┘
                                           │
                                           ▼
                          ┌────────────────────────────────┐
                          │ Enhanced TOC Matching          │
                          │ ├─exact match (numbering)      │
                          │ ├─exact match (title)          │
                          │ ├─fuzzy match (0.8+ ratio)     │
                          │ ├─confidence aware (>0.75)     │
                          │ └─footer-aware (skip footer)   │
                          └──────┬───────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────────┐
                    │ Classification             │
                    │ ├─matched_exact            │
                    │ ├─matched_fuzzy            │
                    │ ├─demoted (not in TOC)     │
                    │ └─unmatched_toc            │
                    └──────┬─────────────────────┘
                           │
                           ▼
                ┌──────────────────────────────┐
                │ Generate Markdown            │
                │ ├─matched → correct level    │
                │ ├─demoted → plain text       │
                │ ├─text/list/table → preserve │
                │ └─footers → skip             │
                └──────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │ Quality Report                   │
        │ ├─extraction quality             │
        │ ├─confidence issues              │
        │ ├─detected footers               │
        │ ├─match results (exact/fuzzy)    │
        │ ├─unmatched TOC entries          │
        │ └─recommendations                │
        └──────┬───────────────────────────┘
               │
               ▼
    ┌─────────────────────────────────┐
    │ OUTPUT                          │
    │ ├─fixed_markdown.md             │
    │ ├─fixed_report.json             │
    │ └─quality_report.json (new)     │
    └─────────────────────────────────┘

✅ BENEFITS:
+ Work with original PDF extraction (better quality)
+ Detect and skip footers
+ Proper spatial ordering
+ Confidence-aware matching
+ Detailed quality metrics
+ No additional API calls
```

## Module Structure

```
docstruct/
├─ pipeline/
│  ├─ json_parser.py         (NEW)
│  │  ├─ parse_mineru_json()
│  │  ├─ extract_text()
│  │  ├─ get_ocr_score()
│  │  └─ is_likely_footer()
│  │
│  ├─ md_fixer.py            (ENHANCED)
│  │  ├─ match_toc_entry()   (updated for JSON)
│  │  ├─ apply_corrections() (footer-aware)
│  │  └─ generate_report()   (enhanced)
│  │
│  └─ reader.py             (unchanged)
│
├─ cli/
│  └─ main.py               (ENHANCED)
│     ├─ add --json-data flag
│     ├─ add --report flag
│     └─ call enhanced logic
│
└─ models/
   └─ results.py            (might extend for quality report)
```

## Data Flow

```
JSON PARSING PHASE
──────────────────
pdf_data.json
    │
    ├─[iterate pages]
    │   │
    │   └─[iterate blocks]
    │       │
    │       ├─extract text (aggregate spans)
    │       ├─get min OCR score
    │       ├─check if footer (Y < 50 or Y > 791)
    │       └─store block info
    │
    ├─[filter]
    │   ├─skip footers
    │   ├─skip low confidence (< 0.60)
    │   └─keep valid blocks
    │
    └─[sort]
        └─by (page_idx, bbox[1])
            → Cleaned Blocks


MATCHING PHASE
──────────────
Cleaned Blocks + TOC Entries
    │
    ├─[for each TOC entry]
    │   │
    │   ├─[try exact match]
    │   │   ├─numbering match? (Art. 1 in block)
    │   │   └─title match? (full string)
    │   │
    │   └─[if no exact, try fuzzy]
    │       ├─similarity ratio > 0.80?
    │       └─confidence > 0.75?
    │
    └─→ Match results (exact/fuzzy/none)


MARKDOWN GENERATION PHASE
─────────────────────────
Matched blocks + TOC info
    │
    ├─[for each cleaned block]
    │   │
    │   ├─[if title type]
    │   │   ├─matched in TOC?
    │   │   │   ├─Yes → add heading with correct level
    │   │   │   │       (# = section, ## = article, etc.)
    │   │   │   └─No → remove heading marker, plain text
    │   │   │
    │   │   └─confidence issue?
    │   │       └─flag in report
    │   │
    │   └─[if text/list/table type]
    │       └─preserve content as-is
    │
    └─→ Markdown lines


REPORTING PHASE
───────────────
Matching results + Cleaned blocks
    │
    ├─[extraction quality]
    │   ├─total blocks parsed
    │   ├─titles found
    │   ├─footers detected
    │   └─low confidence blocks
    │
    ├─[confidence analysis]
    │   ├─excellent (> 0.95)
    │   ├─good (0.80-0.95)
    │   └─borderline (0.60-0.80)
    │
    ├─[matching results]
    │   ├─matched exact
    │   ├─matched fuzzy
    │   ├─demoted non-TOC
    │   └─unmatched TOC entries
    │
    └─→ Quality Report JSON
```

## File Flow Example

### Input
```
data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json
└─ 24 pages, 269 blocks, OCR scores, spatial coords

output/toc_output.json
└─ Extracted TOC with 24 entries (kind, numbering, content)

output/MinerU_markdown_Bando_Borse_di_studio_2025-2026_ENG_2029898716306407424.md
└─ Original markdown (might have errors)
```

### Processing
```
json_parser.py
  ├─ Reads: data/MinerU_*.json
  ├─ Parses: 269 blocks
  ├─ Filters: removes footers (1), skips low-conf (0)
  └─ Returns: 268 valid blocks sorted by position

md_fixer.py (enhanced)
  ├─ Reads: 268 JSON blocks + 24 TOC entries
  ├─ Matches: 18 exact + 2 fuzzy + 6 demoted + 0 missing
  ├─ Generates: corrected markdown with proper levels
  └─ Reports: match results, confidence issues

quality_report.py
  ├─ Collects: extraction metrics
  ├─ Flags: 1 low-confidence title (0.89)
  ├─ Detects: 1 potential footer
  └─ Creates: detailed report
```

### Output
```
output/fixed/
├─ MinerU_markdown_Bando_Borse_di_studio_2025-2026_ENG_2029898716306407424.md
│  └─ Fixed markdown with correct heading hierarchy
│
├─ MinerU_markdown_Bando_Borse_di_studio_2025-2026_ENG_2029898716306407424_report.json
│  └─ Correction report (existing format)
│
└─ MinerU_markdown_Bando_Borse_di_studio_2025-2026_ENG_2029898716306407424_quality.json
   └─ Quality report (new)
      ├─ extraction_quality
      ├─ confidence_analysis
      ├─ matching_results
      └─ recommendations
```

## CLI Usage Evolution

### Current (Feature 002)
```bash
python -m docstruct fix source.md --toc toc.json --output-dir output/
```

### Enhanced (Feature 003)
```bash
# Simple usage (JSON auto-detected from toc.json directory)
python -m docstruct fix source.md --toc toc.json --json-data pdf_data.json --output-dir output/

# With quality report
python -m docstruct fix source.md --toc toc.json --json-data pdf_data.json --report --output-dir output/

# Batch processing (all documents in data/ with JSON)
python scripts/run_pipeline_all.py --skip-extract --use-json
```

## Testing Strategy

```
Unit Tests (test_json_parser.py - NEW)
├─ parse_mineru_json() with sample JSON
├─ extract_text() aggregation
├─ footer detection heuristics
└─ score extraction

Integration Tests (test_md_fixer.py - ENHANCED)
├─ match_toc_entry with JSON blocks
├─ footer awareness in matching
├─ confidence-aware matching thresholds
├─ quality report generation
└─ end-to-end with sample JSON + TOC

Functional Tests (test_pipeline.py - ENHANCED)
├─ Full pipeline with JSON
├─ Report generation and validation
├─ Batch processing with JSON
└─ Comparison: JSON-based vs markdown-only
```

## Performance Considerations

```
Current (markdown-based):
- Time: Fast (regex matching, no parsing)
- Memory: Low (text only)
- Accuracy: Limited (corrupted source)
- Quality: Unknown

Enhanced (JSON-based):
- Time: ~1s JSON parsing + same matching time = negligible overhead
- Memory: ~2-3x (full block metadata, but still < 10MB)
- Accuracy: Higher (original extraction)
- Quality: Quantified with metrics

Trade-off: +1 second, +5-10MB memory → +20% accuracy improvement (worth it)
```

## Backwards Compatibility

```
The enhanced pipeline is BACKWARDS COMPATIBLE:

✅ If --json-data NOT provided:
   - Falls back to current markdown-only approach
   - Existing behavior preserved
   - No breaking changes

✅ If --json-data PROVIDED:
   - Uses enhanced parsing and matching
   - Better results
   - New report available

✅ CLI updates are additive:
   - No existing flags changed
   - New flags are optional
   - Existing scripts continue to work
```

This allows gradual adoption and easy rollback.
