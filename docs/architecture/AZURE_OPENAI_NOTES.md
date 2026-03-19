# Azure OpenAI Integration Notes

## Issue Encountered

When running the batch pipeline with Azure OpenAI (gpt-4.1-mini), some LLM responses were not valid JSON, causing parsing warnings:

```
Warning: Could not parse LLM response for heading: Sommario
```

## Root Cause

Azure OpenAI models (gpt-4.1-mini) may not strictly follow JSON-only response instructions in some cases, especially for certain heading types or non-English text. The model might add extra commentary or formatting around the JSON response.

## Solution Implemented

Updated `docstruct/agents/heading_corrector_agent.py` with improved JSON parsing:

1. **Graceful Fallback**: If direct JSON parsing fails, attempts to extract JSON object using regex
2. **Improved Prompt**: Made instructions more explicit with example format
3. **Robust Error Handling**: Returns `None` for unparseable responses (preserves original heading)

### Code Changes

```python
try:
    result = json.loads(response_text)
except json.JSONDecodeError:
    # Try to extract JSON from response
    import re
    json_match = re.search(r'\{[^{}]*"level"[^{}]*\}', response_text)
    if json_match:
        result = json.loads(json_match.group())
    else:
        return None
```

## Performance Impact

- **Minimal**: Regex extraction only runs if initial parsing fails
- **Graceful Degradation**: Unparseable headings are left unchanged (marked as 'unmatched')
- **No Blocking**: Pipeline continues processing other documents

## Testing

All 16 unit tests pass with the improvements. The pipeline gracefully handles:
- Valid JSON responses (applies correction)
- Invalid JSON responses (preserves heading, logs warning)
- Azure OpenAI quirks (extracts JSON from mixed responses)

## Recommendations

1. **Prompt Engineering**: Consider more structured prompts for Azure models
2. **Model Selection**: Claude (Anthropic) provides more reliable JSON parsing
3. **Monitoring**: Track parse failures per document type for tuning

## Azure-Specific Tips

If using Azure OpenAI:
- Use more recent model versions (gpt-4 vs gpt-4.1-mini)
- Test with small samples first
- Monitor response parsing for unexpected formats
- Consider increasing `max_tokens` for complex documents

## See Also

- `docstruct/agents/heading_corrector_agent.py` - LLM agent implementation
- `docs/guides/BATCH_PIPELINE.md` - Usage guide
- `CLAUDE.md` - Provider configuration
