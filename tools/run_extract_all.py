#!/usr/bin/env python
"""Extract TOC JSON for all markdown files in a directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def find_markdown_files(data_dir: Path) -> list[Path]:
    return sorted(path for path in data_dir.glob("*.md") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TOC JSON for all markdown files in a directory")
    parser.add_argument("--data-dir", default="data", help="Directory containing markdown files")
    parser.add_argument("--output-dir", default="output", help="Directory where extraction JSON files are written")
    args = parser.parse_args()

    data_dir = PROJECT_ROOT / args.data_dir
    output_dir = PROJECT_ROOT / args.output_dir
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        raise SystemExit(1)

    markdown_files = find_markdown_files(data_dir)
    if not markdown_files:
        print(f"No markdown files found in: {data_dir}")
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    successes = 0
    failures = 0
    for index, markdown_file in enumerate(markdown_files, start=1):
        output_path = output_dir / f"{markdown_file.stem}.json"
        print(f"\n[{index}/{len(markdown_files)}] Extracting: {markdown_file.name}")
        cmd = [
            sys.executable,
            "-m",
            "docstruct",
            "extract",
            str(markdown_file),
            "--output",
            str(output_path),
        ]
        result = subprocess.run(cmd, env=env)
        if result.returncode == 0:
            successes += 1
        else:
            failures += 1

    print("\nExtraction complete")
    print(f"Successful: {successes}/{len(markdown_files)}")
    print(f"Failed: {failures}/{len(markdown_files)}")
    if failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

