# Batch Pipeline Runner

Automate TOC extraction and markdown fixing for all documents in the `/data` directory.

## Quick Start

### Run Full Pipeline (Extract TOC + Fix Markdown)

```bash
# Using Python directly (requires ANTHROPIC_API_KEY set)
PYTHONNOUSERSITE=1 python scripts/run_pipeline_all.py

# Using bash wrapper
bash scripts/run_pipeline_all.sh
```

### Only Extract TOC (Skip Markdown Fixing)

```bash
python scripts/run_pipeline_all.py --skip-fix
```

### Only Fix Markdown (Skip TOC Extraction)

Use existing TOC files to fix markdown:

```bash
python scripts/run_pipeline_all.py --skip-extract --no-llm
```

### Fix Markdown with LLM-Based Heading Correction

Use LLM agent for intelligent heading level determination (requires ANTHROPIC_API_KEY):

```bash
python scripts/run_pipeline_all.py --skip-extract
```

## Command Options

```
--skip-extract    Skip TOC extraction (use existing JSON files in output/)
--skip-fix        Skip markdown fixing (only extract TOC)
--no-llm          Skip LLM-based heading correction in markdown fixer
```

## Environment Setup

### Set Anthropic API Key (Required for TOC Extraction)

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Windows (CMD)
set ANTHROPIC_API_KEY=sk-ant-...
```

### Configure LLM Provider (Optional)

By default, uses Anthropic Claude. To use Azure OpenAI:

```bash
export LLM_PROVIDER=azure
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=...
export AZURE_OPENAI_DEPLOYMENT=...
export AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

## Workflow Examples

### Example 1: Full Pipeline with Fresh TOC Extraction

```bash
# Extract TOC for all documents + fix markdown with LLM
python scripts/run_pipeline_all.py
```

**Output**:
- `output/*.json` - Extracted TOC for each document
- `output/fixed/*.md` - Fixed markdown files
- `output/fixed/*_report.json` - Correction reports

### Example 2: Batch Fix Existing Documents

Use previously extracted TOC files to fix markdown without API calls:

```bash
# Skip extraction, use existing TOC files, no LLM for heading correction
python scripts/run_pipeline_all.py --skip-extract --no-llm
```

This is fast and doesn't require API calls.

### Example 3: Only Extract TOC

```bash
python scripts/run_pipeline_all.py --skip-fix
```

### Example 4: Fix with Different Configuration

```bash
# Extract TOC with API, then fix markdown without LLM
python scripts/run_pipeline_all.py --no-llm
```

## Output Structure

```
output/
├── *.json                           # Extracted TOC from step 1
├── pipeline_results_TIMESTAMP.json  # Batch run summary
└── fixed/
    ├── *.md                         # Fixed markdown files
    ├── *_report.json                # Per-file correction report
    └── ...
```

### Correction Report Schema

```json
{
  "source_file": "path/to/source.md",
  "output_file": "path/to/fixed.md",
  "total_lines": 1000,
  "lines_changed": 42,
  "lines_demoted": 5,
  "unmatched_toc_entries": ["Article 7.2.1"],
  "corrections": [
    {
      "line_number": 10,
      "original": "Article 1",
      "corrected": "## Article 1",
      "match_method": "exact"
    },
    ...
  ]
}
```

## Performance Notes

### Processing Time Estimates

- **TOC Extraction**: ~2-5 seconds per document (with LLM API)
- **Markdown Fixing**: ~100-500ms per document
  - Without LLM: Fast (just pattern matching)
  - With LLM: Slower (1-2 seconds per heading analyzed)

### Batch Size

All 5 documents can be processed in ~2-5 minutes total:
- Borse di studio (112K): 22 corrections
- Bando di Concorso (140K): 91 corrections
- Competition Notice (170K): TBD
- Notice of competition (518K): TBD
- Bando benefici DSU (904K): TBD

## Troubleshooting

### Error: "anthropic package not installed"

```bash
pip install anthropic
```

### Error: "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Error: "DLL load failed while importing _ssl"

Use the workaround flag:

```bash
PYTHONNOUSERSITE=1 python scripts/run_pipeline_all.py
```

### Error: "TOC file not found and extraction skipped"

When using `--skip-extract`, TOC files must already exist in `output/`:

```bash
# First, extract TOC
python scripts/run_pipeline_all.py --skip-fix

# Then, fix markdown without extraction
python scripts/run_pipeline_all.py --skip-extract --no-llm
```

## Integration Examples

### Processing Results

Results are logged to `output/pipeline_results_TIMESTAMP.json`:

```json
[
  {
    "file": "document.md",
    "toc_extraction": "SUCCESS",
    "markdown_fix": "SUCCESS",
    "corrections": 42
  },
  {
    "file": "document2.md",
    "toc_extraction": "FAILED",
    "error": "No TOC section found"
  }
]
```

### Parsing Results in Python

```python
import json
from pathlib import Path

# Find latest results file
results_files = sorted(Path('output').glob('pipeline_results_*.json'))
latest_results = json.load(open(results_files[-1]))

# Process results
for result in latest_results:
    if result['toc_extraction'] == 'SUCCESS':
        print(f"✓ {result['file']}: {result.get('corrections', 0)} corrections")
    else:
        print(f"✗ {result['file']}: {result.get('error', 'Unknown error')}")
```

## Advanced: Custom Processing

To process documents programmatically:

```python
from pathlib import Path
from docstruct.pipeline.extractor import extract_toc
from docstruct.pipeline.md_fixer import fix_markdown
from docstruct.providers.factory import build_client

# Build client
client = build_client()

# Process single document
md_file = Path('data/document.md')
toc_file = Path('output/document.json')

# Extract TOC
result = extract_toc(str(md_file), client)
with open(toc_file, 'w') as f:
    import json
    json.dump(result.to_dict(), f, indent=2)

# Fix markdown
report = fix_markdown(str(md_file), str(toc_file), 'output/fixed', client=client)
print(f"Corrections: {report.lines_changed}")
```

## Support

For issues with the pipeline runner, check:
1. API key is set: `echo $ANTHROPIC_API_KEY`
2. Internet connectivity for API calls
3. File permissions in `data/` and `output/` directories
4. Sufficient disk space for output files
5. Python environment: `PYTHONNOUSERSITE=1` flag for SSL issues

## See Also

- [LLM Agent Implementation](../architecture/LLM_AGENT_IMPLEMENTATION.md)
- [Markdown Fixer Documentation](../../docstruct/pipeline/md_fixer.py)
- [TOC Extraction Pipeline](../../docstruct/pipeline/extractor.py)
