#!/usr/bin/env python
"""Test JSON loader with sample MinerU file."""

import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from miner_mineru.pipeline.json_loader import load_mineru_json, save_cleaned_json


def main():
    """Load MinerU JSON and save cleaned version."""
    json_file = Path('data/MinerU_Bando_Borse_di_studio_2025-2026_ENG__20260309145918.json')

    if not json_file.exists():
        print(f"Error: {json_file} not found")
        return 1

    print(f"Loading {json_file.name}...")
    doc = load_mineru_json(str(json_file))

    print(f"\nDocument loaded:")
    print(f"  Total pages: {doc.total_pages}")
    print(f"  Total blocks: {len(doc.get_all_blocks())}")

    # Show sample blocks from first page
    if doc.pages:
        page = doc.pages[0]
        print(f"\nFirst page: {len(page.blocks)} blocks")

        for idx, block in enumerate(page.blocks[:3]):
            print(f"\n  Block {idx}:")
            print(f"    Type: {block.type.value}")
            if block.content:
                content_preview = block.content[:60].replace('\n', ' ')
                print(f"    Content: {content_preview}...")
            if block.confidence is not None:
                print(f"    Confidence: {block.confidence:.3f}")
            if block.list_items:
                print(f"    List items: {len(block.list_items)}")
            if block.table:
                print(f"    Table: {len(block.table.get('rows', []))} rows")

    # Save cleaned JSON
    output_path = Path('output/cleaned_blocks.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving cleaned JSON to {output_path}...")
    save_cleaned_json(doc, str(output_path))

    # Show sample of output
    with open(output_path, encoding='utf-8') as f:
        cleaned_data = json.load(f)

    print(f"\nCleaned output sample:")
    print(json.dumps(cleaned_data, indent=2)[:800])

    print(f"\nSuccess! Cleaned JSON saved to {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
