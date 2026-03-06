# MinerU Pipeline Scripts

PowerShell scripts for the MinerU TOC extraction and markdown fixing pipeline.

## Quick Start

### 1. Only Fix Markdown (No LLM Setup)

```powershell
# From repository root
.\scripts\run-fixer.ps1
```

This processes all markdown/TOC file pairs and generates corrected markdown files.

### 2. Complete Pipeline (Extract + Fix)

```powershell
# Set API key first (Anthropic)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Run complete pipeline
.\scripts\run-pipeline.ps1
```

## Scripts

### `run-fixer.ps1`

Fix heading levels in all markdown files using pre-extracted TOC files.

**Usage:**
```powershell
.\scripts\run-fixer.ps1 [options]
```

**Options:**
- `-DataDir <path>` - Directory with markdown files (default: `data`)
- `-OutputDir <path>` - Directory with TOC JSON files (default: `output`)
- `-FixedDir <path>` - Output directory for corrected files (default: `output/fixed`)
- `-Verbose` - Show detailed output

**Example:**
```powershell
# Process with custom directories
.\scripts\run-fixer.ps1 -DataDir "C:\data" -OutputDir "C:\toc" -FixedDir "C:\fixed"
```

**Requirements:**
- Python 3.9+ installed
- `miner_mineru` package available
- Extracted TOC files in output directory

---

### `run-extract.ps1`

Extract table of contents from a markdown file.

**Usage:**
```powershell
.\scripts\run-extract.ps1 -MarkdownFile <file> [options]
```

**Parameters:**
- `-MarkdownFile <path>` - Markdown file to process (required)
- `-OutputFile <path>` - Output JSON path (optional)
- `-Provider <provider>` - LLM provider: `anthropic` or `azure` (default: `anthropic`)

**Examples:**
```powershell
# Extract with Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md"

# Extract with custom output path
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md" -OutputFile "output\notice_toc.json"

# Extract with Azure
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md" -Provider azure
```

**Requirements:**
- Anthropic API key (`$env:ANTHROPIC_API_KEY`)
  OR
- Azure OpenAI credentials

---

### `run-pipeline.ps1`

Complete two-step pipeline: extract TOC and fix markdown.

**Usage:**
```powershell
.\scripts\run-pipeline.ps1 [options]
```

**Options:**
- `-DataDir <path>` - Directory with markdown files (default: `data`)
- `-OutputDir <path>` - Directory for TOC files (default: `output`)
- `-SkipExtraction` - Skip step 1, only run fixer
- `-Provider <provider>` - LLM provider: `anthropic` or `azure` (default: `anthropic`)

**Examples:**
```powershell
# Complete pipeline with Anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.\scripts\run-pipeline.ps1

# Only run fixer (skip extraction)
.\scripts\run-pipeline.ps1 -SkipExtraction

# Use Azure for extraction
.\scripts\run-pipeline.ps1 -Provider azure
```

## Environment Setup

### Anthropic API

```powershell
# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Or in your PowerShell profile
Add-Content $PROFILE @"
`$env:ANTHROPIC_API_KEY = "your-key-here"
"@
```

### Azure OpenAI

```powershell
# Set all required variables
$env:LLM_PROVIDER = "azure"
$env:AZURE_OPENAI_API_KEY = "your-key"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4"
$env:AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# Run pipeline
.\scripts\run-pipeline.ps1 -Provider azure
```

### Python Environment

Activate conda environment:
```powershell
conda activate agent
```

## Output

Each script generates:

1. **Corrected Markdown**: `output/fixed/<filename>.md`
   - Normalized heading levels (H1/H2/H3/H4)
   - Content preserved unchanged

2. **Correction Report**: `output/fixed/<filename>_report.json`
   - Total lines processed
   - Lines changed and demoted
   - Unmatched TOC entries
   - Detailed correction history

## Workflow Examples

### Example 1: Extract Single File, Then Fix

```powershell
# Activate environment
conda activate agent

# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Extract TOC
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md"

# Fix all files with matching TOC
.\scripts\run-fixer.ps1

# View results
Get-ChildItem output\fixed\*.md
```

### Example 2: Complete Batch Pipeline

```powershell
# Activate environment
conda activate agent

# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Run complete pipeline (extract all, then fix all)
.\scripts\run-pipeline.ps1

# Check results
Write-Host "Corrected files:"
Get-ChildItem output\fixed\*.md

Write-Host "`nReports:"
Get-ChildItem output\fixed\*_report.json
```

### Example 3: Only Fix (No Extraction)

```powershell
# Activate environment
conda activate agent

# Run fixer on pre-extracted TOC files
.\scripts\run-fixer.ps1

# View results
Get-ChildItem output\fixed\
```

## Troubleshooting

### "Cannot find python"

Ensure Python is installed and in PATH:
```powershell
python --version
```

Or activate conda environment:
```powershell
conda activate agent
```

### "ANTHROPIC_API_KEY not set"

Set the API key before running:
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md"
```

### "No TOC files found"

Extract TOC files first:
```powershell
.\scripts\run-extract.ps1 -MarkdownFile "data\notice.md"
```

### "Script execution disabled"

Enable script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Files

```
scripts/
  ├── run-fixer.ps1      # Fix markdown (no LLM required)
  ├── run-extract.ps1    # Extract TOC (requires LLM)
  ├── run-pipeline.ps1   # Complete pipeline (extract + fix)
  └── README.md          # This file
```

## Requirements

- **PowerShell 5.0+** (included in Windows 10/11)
- **Python 3.9+** with `miner_mineru` installed
- **Conda** environment activated: `conda activate agent`
- **API Key** for TOC extraction (Anthropic or Azure)

## Support

For issues or questions, see:
- [PIPELINE_GUIDE.md](../PIPELINE_GUIDE.md) - Detailed pipeline documentation
- [tests/test_md_fixer.py](../tests/test_md_fixer.py) - Usage examples
- [CLAUDE.md](../CLAUDE.md) - Project guidelines
