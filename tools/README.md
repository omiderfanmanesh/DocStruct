# Tools

These scripts make it easier to run the multi-stage document pipeline in different scenarios.

## Single-file workflows

- `python tools/run_extract.py <markdown_file>`
  - Extract TOC JSON for one file
- `python tools/run_fix.py <markdown_file> --toc <toc.json>`
  - Fix one file using a previously extracted TOC JSON
- `python tools/run_pipeline.py <markdown_file>`
  - Run extract + fix for one file with staged output folders
- `python tools/run_pageindex.py`
  - Build only the PageIndex search indexes from fixed markdown
- `python tools/run_search_agent.py "your question"`
  - Ask the document-search agent and save the answer artifact

## Batch workflows

- `python tools/run_extract_all.py`
  - Extract TOC JSON for every markdown file in `data/`
- `python tools/run_fixer.py`
  - Fix every markdown file that already has matching TOC JSON in `output/`
- `python tools/run_pipeline_all.py`
  - Full batch pipeline for all markdown files in `data/`

## Validation workflow

- `python tools/smoke_test.py <markdown_file>`
  - Run a quick extract/fix/pipeline smoke test on one real document

## Typical usage

### Scenario 1: extract only

```powershell
python tools/run_extract.py .\data\my-doc.md
```

### Scenario 2: fix only

```powershell
python tools/run_fix.py .\data\my-doc.md --toc .\output\01_toc\my-doc.json
```

### Scenario 3: full single-document pipeline

```powershell
python tools/run_pipeline.py .\data\my-doc.md
```

### Scenario 4: full batch pipeline

```powershell
python tools/run_pipeline_all.py
```

## Output layout

Pipeline artifacts are now separated by stage:

- `output/01_toc/` for extraction JSON
- `output/02_fixed_markdown/` for corrected markdown
- `output/02_fix_reports/` for markdown-fix reports
- `output/03_pageindex/` for PageIndex tree indexes
- `output/04_answers/` for saved search-agent answers
- `output/00_runs/` for batch pipeline summaries
