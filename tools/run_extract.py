#!/usr/bin/env python
"""Extract TOC JSON for a single markdown file."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docstruct.output_layout import TOC_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TOC JSON for a single markdown file")
    parser.add_argument("markdown_file", help="Path to markdown file")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output JSON path (default: output/<stem>.json)",
    )
    args = parser.parse_args()

    markdown_file = Path(args.markdown_file)
    if not markdown_file.is_absolute():
        markdown_file = (PROJECT_ROOT / markdown_file).resolve()
    if not markdown_file.exists():
        print(f"ERROR: File not found: {markdown_file}")
        raise SystemExit(1)

    output_path = Path(args.output) if args.output else PROJECT_ROOT / TOC_DIR / f"{markdown_file.stem}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        "-m",
        "docstruct",
        "extract",
        str(markdown_file),
        "--output",
        str(output_path),
    ]

    print(f"Extracting: {markdown_file}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(f"Saved TOC JSON to: {output_path}")


if __name__ == "__main__":
    main()

