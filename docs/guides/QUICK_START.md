# Quick Start: Batch Pipeline

## One-Line Commands

### Process All Documents (with LLM heading correction)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/run_pipeline_all.py
```

### Fast Processing (no API calls, no LLM)
```bash
python scripts/run_pipeline_all.py --skip-extract --no-llm
```

### Extract TOC Only
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/run_pipeline_all.py --skip-fix
```

## What It Does

**Input**: All `.md` files in `/data`

**Output**:
- `/output/fixed/*.md` - Fixed markdown files with corrected heading levels
- `/output/fixed/*_report.json` - Detailed correction reports
- `/output/pipeline_results_*.json` - Batch processing summary

## Results Example

```
Bando_Borse_di_studio (112K)      → 22 lines corrected ✓
Bando_di_Concorso (140K)          → 91 lines corrected ✓
Competition_Notice (170K)          → (needs TOC extraction)
Notice_of_competition (518K)       → (needs TOC extraction)
Bando_benefici_DSU (904K)          → (needs TOC extraction)
```

## Key Features

✅ **LLM-Based Heading Correction** - Claude analyzes document structure
✅ **Batch Processing** - All documents in one command
✅ **Flexible Options** - Skip extraction, skip fixing, or skip LLM
✅ **Detailed Reports** - JSON output with per-file corrections
✅ **Fast Fallback** - Can process without API calls when TOC exists

## Files

- **Script**: `scripts/run_pipeline_all.py` - Main batch processor
- **Docs**:
  - `docs/guides/BATCH_PIPELINE.md` - Comprehensive guide
  - `docs/architecture/PIPELINE_SUMMARY.md` - Complete overview
  - `docs/architecture/LLM_AGENT_IMPLEMENTATION.md` - Technical details

## Troubleshooting

**Error: "anthropic package not installed"**
```bash
pip install anthropic
```

**Error: "ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

**SSL Error (DLL load failed)**
```bash
PYTHONNOUSERSITE=1 python scripts/run_pipeline_all.py
```

## See Also

- `docs/guides/BATCH_PIPELINE.md` - Full documentation with all options
- `docs/architecture/PIPELINE_SUMMARY.md` - Architecture and design overview
- `docstruct/cli/main.py` - CLI entry points
- `tests/test_md_fixer.py` - Test examples
