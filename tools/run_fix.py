#!/usr/bin/env python
"""Fix headings for a single markdown file using an existing TOC JSON file."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix a single markdown file using an extracted TOC JSON file")
    parser.add_argument("markdown_file", help="Path to markdown file")
    parser.add_argument("--toc", required=True, help="Path to TOC JSON file")
    parser.add_argument(
        "--output-dir",
        "-o",
        default="output/fixed",
        help="Directory where corrected markdown and report will be written",
    )
    args = parser.parse_args()

    markdown_file = Path(args.markdown_file)
    toc_file = Path(args.toc)
    if not markdown_file.is_absolute():
        markdown_file = (PROJECT_ROOT / markdown_file).resolve()
    if not toc_file.is_absolute():
        toc_file = (PROJECT_ROOT / toc_file).resolve()

    if not markdown_file.exists():
        print(f"ERROR: File not found: {markdown_file}")
        raise SystemExit(1)
    if not toc_file.exists():
        print(f"ERROR: TOC file not found: {toc_file}")
        raise SystemExit(1)

    output_dir = (PROJECT_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        "-m",
        "docstruct",
        "fix",
        str(markdown_file),
        "--toc",
        str(toc_file),
        "--output-dir",
        str(output_dir),
    ]

    print(f"Fixing: {markdown_file}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(f"Saved corrected outputs to: {output_dir}")


if __name__ == "__main__":
    main()

