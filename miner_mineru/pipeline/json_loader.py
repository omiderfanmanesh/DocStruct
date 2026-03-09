"""Load and clean MinerU JSON extraction files.

This module handles:
1. Loading raw MinerU JSON files
2. Removing unnecessary spatial/metadata keys (bbox, angle, index, lines structure)
3. Extracting essential data (type, content, table, list)
4. Building clean Block objects for further processing
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from miner_mineru.models.blocks import Block, BlockType, ListItem, Table, TableRow, TableCell
from miner_mineru.models.pages import Page, Document


def _extract_text_from_spans(lines: List[Dict[str, Any]]) -> str:
    """Extract and join text content from lines and spans structure.

    Args:
        lines: List of line objects containing spans with content

    Returns:
        Joined text content
    """
    text_parts = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get('spans', [])
        for span in spans:
            if isinstance(span, dict) and 'content' in span:
                text_parts.append(span['content'])
    return ' '.join(text_parts)


def _extract_min_confidence(lines: List[Dict[str, Any]]) -> Optional[float]:
    """Extract minimum OCR confidence score from spans.

    Args:
        lines: List of line objects containing spans with scores

    Returns:
        Minimum confidence score, or None if not available
    """
    scores = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get('spans', [])
        for span in spans:
            if isinstance(span, dict) and 'score' in span:
                scores.append(span['score'])

    return min(scores) if scores else None


def _extract_block_items(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract list items from nested blocks.

    Args:
        blocks: List of nested block objects

    Returns:
        List of items with content
    """
    items = []

    if not isinstance(blocks, list):
        return items

    for idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue

        # Extract text from block lines
        block_text = _extract_text_from_spans(block.get('lines', []))
        if block_text:
            items.append({
                'index': idx,
                'content': block_text
            })

    return items


def _extract_html_table(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract HTML table from nested blocks.

    MinerU tables contain HTML content in the spans.

    Args:
        blocks: List of nested block objects (table content)

    Returns:
        Table structure with HTML content, or None
    """
    if not isinstance(blocks, list) or not blocks:
        return None

    # Extract HTML from spans
    html_content = ""
    for block in blocks:
        if not isinstance(block, dict):
            continue

        for line in block.get('lines', []):
            if not isinstance(line, dict):
                continue

            for span in line.get('spans', []):
                if isinstance(span, dict):
                    if 'html' in span:
                        html_content += span['html']
                    elif 'content' in span:
                        html_content += span['content']

    if not html_content:
        return None

    return {
        'html': html_content
    }


def _clean_block(
    block_data: Dict[str, Any],
    block_id: str,
    page_idx: int
) -> Optional[Block]:
    """Convert raw MinerU block to cleaned Block object.

    Removes unnecessary keys (bbox, angle, index) and extracts:
    - type
    - content (from lines/spans)
    - table (if table_cells present)
    - list (if list_items present)

    Args:
        block_data: Raw block from MinerU JSON
        block_id: Unique block identifier
        page_idx: Page index

    Returns:
        Cleaned Block object, or None if invalid
    """
    if not isinstance(block_data, dict):
        return None

    # Get block type
    block_type_str = block_data.get('type', 'text')
    try:
        block_type = BlockType(block_type_str)
    except ValueError:
        block_type = BlockType.UNKNOWN

    # Extract content from lines/spans
    lines = block_data.get('lines', [])
    content = _extract_text_from_spans(lines) if lines else None

    # Extract confidence
    confidence = _extract_min_confidence(lines)

    # Extract list items (from nested blocks)
    list_items = []
    table = None

    nested_blocks = block_data.get('blocks', [])
    if nested_blocks:
        if block_type == BlockType.LIST:
            list_items = _extract_block_items(nested_blocks)
        elif block_type == BlockType.TABLE:
            table = _extract_html_table(nested_blocks)

    # Create block
    block = Block(
        block_id=block_id,
        page_idx=page_idx,
        type=block_type,
        content=content,
        confidence=confidence,
        list_items=list_items if list_items else [],
        table=table,
        source_spans_count=len([
            s for line in lines if isinstance(line, dict)
            for s in line.get('spans', [])
            if isinstance(s, dict)
        ]) if lines else 0
    )

    return block


def load_mineru_json(json_path: str) -> Document:
    """Load and clean MinerU JSON extraction file.

    Removes unnecessary keys (bbox, angle, index, etc.) and extracts:
    - type: block type (title, text, table, list, equation)
    - content: text content (aggregated from spans)
    - table: table structure (if applicable)
    - list: list items (if applicable)

    Args:
        json_path: Path to MinerU JSON file

    Returns:
        Cleaned Document object with cleaned blocks

    Raises:
        FileNotFoundError: If JSON file not found
        json.JSONDecodeError: If JSON is invalid
    """
    path = Path(json_path)

    with open(path, encoding='utf-8') as f:
        raw_data = json.load(f)

    # Create document
    doc = Document(
        source_file=str(path),
        total_pages=0
    )

    # Extract pages from pdf_info (MinerU format has pdf_info key)
    if isinstance(raw_data, dict) and 'pdf_info' in raw_data:
        pages_data = raw_data['pdf_info']
    elif isinstance(raw_data, list):
        pages_data = raw_data
    else:
        raise ValueError(f"Expected dict with 'pdf_info' or list of pages, got {type(raw_data)}")

    # Process pages
    if not isinstance(pages_data, list):
        raise ValueError(f"Expected list of pages, got {type(pages_data)}")

    for page_idx, page_data in enumerate(pages_data):
        if not isinstance(page_data, dict):
            continue

        # Create page
        page = Page(
            page_idx=page_idx,
            page_width=page_data.get('page_size', [0, 0])[0],
            page_height=page_data.get('page_size', [0, 0])[1] if len(page_data.get('page_size', [])) > 1 else None
        )

        # Process blocks
        para_blocks = page_data.get('para_blocks', [])
        if not isinstance(para_blocks, list):
            continue

        for block_idx, block_data in enumerate(para_blocks):
            if not isinstance(block_data, dict):
                continue

            # Create block ID
            block_id = f"page_{page_idx}_block_{block_idx}"

            # Clean block
            block = _clean_block(block_data, block_id, page_idx)
            if block:
                page.blocks.append(block)

        doc.pages.append(page)

    doc.total_pages = len(doc.pages)
    return doc


def save_cleaned_json(doc: Document, output_path: str) -> None:
    """Save cleaned document to JSON file.

    Args:
        doc: Cleaned Document object
        output_path: Output JSON file path
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)
