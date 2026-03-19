# LLM Agent Implementation for Heading Correction

## Overview
Refactored the markdown fixer from regex-based heading level inference to an intelligent LLM agent-based approach. The system now uses Claude to analyze document structure and determine correct heading levels for unmatched headings.

## Key Changes

### 1. New Agent Module: `docstruct/agents/heading_corrector_agent.py`
**Purpose**: Encapsulates LLM-based heading level determination

**Key Functions**:
- `build_heading_correction_prompt()` - Constructs intelligent prompt with document context
  - Includes heading level mapping (H1-H4 with examples)
  - Shows available TOC structure for reference
  - Provides recent document context (last 5 headings)
  - Requests JSON response with heading level and confidence score

- `correct_heading_with_llm()` - Calls Claude API and parses response
  - Uses claude-3-5-sonnet-20241022 model
  - Returns heading level (1-4) if confidence >= 0.6
  - Handles JSON parsing errors gracefully
  - Returns None if confidence is too low or response cannot be parsed

### 2. Modified Pipeline: `docstruct/pipeline/md_fixer.py`

**Function Signature Changes**:
```python
# OLD: apply_all_corrections(source_lines, matched_pairs)
# NEW: apply_all_corrections(source_lines, matched_pairs, toc_entries, client=None)
```

**Implementation Updates**:
- Removed regex-based `infer_heading_level_from_text()` function
- Replaced with call to `infer_heading_level_with_llm(client, heading_text, context_headings, toc_entries)`
- Added context tracking: maintains list of recent headings (max 10) for better LLM decision-making
- Updated `CorrectionEntry.match_method` to use 'llm_inferred' instead of 'inferred'
- Made client parameter optional (client=None) for backward compatibility
- Updated `fix_markdown()` signature: `fix_markdown(source_path, toc_json_path, output_dir, client=None)`

**Heading Inference Logic**:
1. Matched headings → re-level based on TOC kind mapping
2. Unmatched headings BEFORE first TOC match → demoted to plain text (cover page junk)
3. Unmatched headings AFTER first TOC match → use LLM with document context
4. If LLM returns valid decision → apply it, otherwise preserve as-is

### 3. Updated CLI: `docstruct/cli/main.py`

**Changes**:
```python
# Build LLM client before processing
client = build_client()

# Pass client to fix_markdown
report = fix_markdown(args.markdown_file, args.toc, args.output_dir, client=client)
```

**LLM Provider Support**:
- Uses `factory.build_client()` to read `LLM_PROVIDER` environment variable
- Supports: `anthropic` (default) and `azure`
- Handles API key validation before processing

### 4. Updated Tests: `tests/test_md_fixer.py`

**Test Status**: All 16 tests passing ✅

**Key Updates**:
- Removed old regex-based tests for `infer_heading_level_from_text`
- Updated function calls to pass new parameters:
  ```python
  apply_all_corrections(source_lines, matched_pairs, toc_entries, client=None)
  ```
- Tests now verify:
  - Heading level mapping (kind → level conversion)
  - Content preservation (paragraphs, tables, lists)
  - Correction report structure and accuracy
  - Integration with real fixtures

## How It Works

### Context-Aware Heading Analysis
When an unmatched heading is encountered after the first TOC match:

1. **Build Context**: Collect recent headings (last 5 from document)
2. **Gather Reference**: Include all TOC entries for structure reference
3. **Create Prompt**: Generate detailed prompt with:
   - Heading to analyze
   - Heading level mapping guidelines
   - Available TOC structure
   - Recent document context
4. **Call LLM**: Send to Claude for intelligent analysis
5. **Parse Response**: Extract level and confidence from JSON response
6. **Validate**: Only use response if confidence >= 0.6 and level is valid (1-4)
7. **Apply/Preserve**: Apply corrected level or preserve original if LLM unsure

### Example Prompt Section
```
## Heading to Analyze:
Discussion of Results

## Heading Level Mapping:
- Level 1 (#): Major sections, main categories (SECTION, PART, CHAPTER, ANNEX)
- Level 2 (##): Main divisions, articles (ARTICLE, ART., TITLE within section)
- Level 3 (###): Subsections, subarticles (PARA, SUBSECTION, ART. X(Y))
- Level 4 (####): Details, items, points (ITEM, CLAUSE, SUB-PARA)

## Document Context (recent headings):
1. # Introduction
2. ## Background
3. ## Methodology
```

## API Integration

**Building Client**:
```python
from docstruct.providers.factory import build_client

client = build_client()  # Reads LLM_PROVIDER env var
```

**Provider Configuration**:
```bash
# Anthropic (default)
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI
export LLM_PROVIDER=azure
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=...
export AZURE_OPENAI_DEPLOYMENT=...
```

## Advantages Over Regex Approach

1. **Semantic Understanding**: Claude understands document structure and meaning
2. **Context Awareness**: Uses surrounding headings to make intelligent decisions
3. **Flexible Hierarchy**: Handles complex document structures naturally
4. **Confidence Scoring**: Only applies corrections when confident
5. **Graceful Degradation**: Preserves heading if LLM is uncertain
6. **Maintainability**: No brittle regex patterns to update

## Testing & Validation

All tests pass with the new implementation:
- ✅ Heading re-leveling based on TOC kind mapping
- ✅ Content preservation (paragraphs, tables, lists)
- ✅ Correction report generation and JSON serialization
- ✅ Integration with markdown files and fixtures
- ✅ Graceful handling of unmatched content

## Backward Compatibility

- Client parameter is optional (defaults to None)
- If client=None, LLM inference is skipped (preserves unmatched headings as-is)
- All other functionality remains unchanged
- Existing scripts continue to work without modification

## Known Limitations & Future Improvements

1. **Environment Setup**: Current conda environment has typing_extensions conflict
   - Workaround: Use PYTHONNOUSERSITE=1 flag
   - Plan: Resolve dependency issues in environment setup

2. **Confidence Threshold**: Currently fixed at 0.6
   - Could be made configurable for different document types

3. **Token Usage**: Using claude-3-5-sonnet model
   - More cost-effective than larger models
   - Could switch to faster/cheaper models if needed

4. **Batch Processing**: Currently processes headings one at a time
   - Could be optimized with batch requests in future

## Files Modified
- `docstruct/agents/heading_corrector_agent.py` (NEW)
- `docstruct/pipeline/md_fixer.py` (MODIFIED)
- `docstruct/cli/main.py` (MODIFIED)
- `tests/test_md_fixer.py` (MODIFIED)

## Verification Commands
```bash
# Run all tests
PYTHONNOUSERSITE=1 python -m pytest tests/test_md_fixer.py -v -p no:anyio

# Test CLI help
python -m docstruct fix --help

# Generate test prompt
python -c "from docstruct.agents.heading_corrector_agent import build_heading_correction_prompt; print(build_heading_correction_prompt('Test', [], []))"
```
