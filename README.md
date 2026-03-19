# Miner-MinerU

Intelligent TOC extraction and markdown fixing pipeline for MinerU-generated documents.

## Quick Start

```bash
# Fast batch processing (no API calls, uses existing TOC files)
python scripts/run_pipeline_all.py --skip-extract --no-llm

# Full pipeline with LLM heading correction
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/run_pipeline_all.py
```

## What It Does

1. **Extracts TOC** from markdown documents using Claude LLM
2. **Fixes Headings** using intelligent LLM-based analysis
3. **Generates Reports** with detailed correction information

**Results**: 113+ heading corrections across tested documents

## Documentation

Start here: **[docs/README.md](./docs/README.md)**

Key guides:
- **Quick Start**: [docs/guides/QUICK_START.md](./docs/guides/QUICK_START.md)
- **Full Guide**: [docs/guides/BATCH_PIPELINE.md](./docs/guides/BATCH_PIPELINE.md)
- **Architecture**: [docs/architecture/PIPELINE_SUMMARY.md](./docs/architecture/PIPELINE_SUMMARY.md)

## Features

✅ **LLM-Based Heading Correction** - Context-aware analysis with confidence scoring
✅ **Batch Processing** - Process all documents with single command
✅ **Flexible Options** - Skip extraction, skip fixing, or skip LLM as needed
✅ **Detailed Reports** - JSON output with per-line corrections
✅ **Fast Fallback** - Can run without API calls using existing TOC files

## Project Structure

```
docstruct/           # Main Python package
  agents/               # LLM agents for analysis
  models/               # Data models
  pipeline/             # Core processing pipeline
  providers/            # LLM provider abstraction
  cli/                  # Command-line interface

scripts/                # Batch processing scripts
  run_pipeline_all.py   # Main batch runner

docs/                   # Complete documentation
  guides/               # User guides and tutorials
  architecture/         # Technical documentation
  archive/              # Older documentation

tests/                  # Test suite (16 tests, all passing)

data/                   # Input markdown files
output/                 # Pipeline output (TOC, fixed markdown, reports)
```

## Commands

### Batch Processing
```bash
# All options
python scripts/run_pipeline_all.py [--skip-extract] [--skip-fix] [--no-llm]

# Examples:
python scripts/run_pipeline_all.py                           # Full pipeline
python scripts/run_pipeline_all.py --skip-extract --no-llm   # Fast fix only
python scripts/run_pipeline_all.py --skip-fix                # Extract TOC only
```

### Single Document
```bash
# Extract TOC
python -m docstruct extract data/document.md --output output/document.json

# Fix markdown
python -m docstruct fix data/document.md --toc output/document.json --output-dir output/fixed
```

### Tests
```bash
PYTHONNOUSERSITE=1 python -m pytest tests/ -v -p no:anyio
```

## Environment Setup

### Required for TOC Extraction
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Optional: Different LLM Provider
```bash
export LLM_PROVIDER=azure  # default: anthropic
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=...
export AZURE_OPENAI_DEPLOYMENT=...
```

## Test Results

✅ **Unit Tests**: 16/16 passing (100%)
✅ **Integration Tests**: Verified with real documents
✅ **Corrections**: 113+ lines corrected across tested documents

## Performance

- **TOC Extraction**: ~2-5 seconds per document (with LLM)
- **Markdown Fixing**: ~100-500ms per document
  - Without LLM: <200ms
  - With LLM: 1-2 seconds per heading analyzed

## Known Issues

- Conda environment has `typing_extensions` conflict - use `PYTHONNOUSERSITE=1` flag
- SSL DLL issues on Windows - also use `PYTHONNOUSERSITE=1` flag

## Status

✅ **COMPLETE & TESTED**
- All features implemented
- All tests passing
- Documentation complete
- Batch processing verified

For detailed information, see [docs/README.md](./docs/README.md).
