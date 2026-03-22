#!/usr/bin/env python
"""Ask grounded questions across indexed documents and save the answer artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docstruct.application.pageindex_workflow import answer_question
from docstruct.infrastructure.llm.factory import build_client
from docstruct.output_layout import ANSWERS_DIR, PAGEINDEX_DIR, ensure_output_layout, slugify


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Ask the DocStruct document-search agent about indexed documents")
    parser.add_argument("question", help="Question to ask")
    parser.add_argument("--index-dir", "-i", default=str(PAGEINDEX_DIR), help="Directory containing PageIndex search indexes")
    parser.add_argument("--output", "-o", default=None, help="Optional explicit output JSON file path")
    args = parser.parse_args()

    layout = ensure_output_layout(PROJECT_ROOT)
    index_dir = Path(args.index_dir)
    if not index_dir.is_absolute():
        index_dir = (PROJECT_ROOT / index_dir).resolve()

    client = build_client()
    answer = answer_question(args.question, str(index_dir), client)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = (PROJECT_ROOT / output_path).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = layout["answers"] / f"{timestamp}_{slugify(args.question)}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(answer.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(answer.to_dict(), indent=2, ensure_ascii=False))
    print(f"\nSaved answer to: {output_path}")


if __name__ == "__main__":
    main()
