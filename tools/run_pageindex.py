#!/usr/bin/env python
"""Build PageIndex-backed search indexes from fixed markdown only."""

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

from docstruct.output_layout import FIXED_MARKDOWN_DIR, PAGEINDEX_DIR, TOC_DIR, ensure_output_layout


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PageIndex-backed search indexes from fixed markdown")
    parser.add_argument("path", nargs="?", default=str(FIXED_MARKDOWN_DIR), help="Markdown file or directory to index")
    parser.add_argument("--output-dir", "-o", default=str(PAGEINDEX_DIR), help="Directory where PageIndex JSON files will be written")
    parser.add_argument("--toc-dir", default=str(TOC_DIR), help="Directory containing DocStruct extraction JSON files")
    args = parser.parse_args()

    ensure_output_layout(PROJECT_ROOT)

    target = Path(args.path)
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    if not target.exists():
        print(f"ERROR: Input path not found: {target}")
        raise SystemExit(1)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    toc_dir = Path(args.toc_dir)
    if not toc_dir.is_absolute():
        toc_dir = (PROJECT_ROOT / toc_dir).resolve()

    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        "-m",
        "docstruct",
        "index",
        str(target),
        "--output-dir",
        str(output_dir),
        "--toc-dir",
        str(toc_dir),
    ]

    print(f"Indexing PageIndex trees from: {target}")
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(f"Saved PageIndex outputs to: {output_dir}")


if __name__ == "__main__":
    main()
