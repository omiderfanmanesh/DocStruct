#!/usr/bin/env python
"""Quick smoke-test runner for common DocStruct scenarios."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def run(cmd: list[str], label: str) -> int:
    print(f"\n=== {label} ===")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, env=env).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run quick smoke tests for DocStruct")
    parser.add_argument("markdown_file", help="Markdown file to use for smoke checks")
    args = parser.parse_args()

    markdown_file = Path(args.markdown_file)
    if not markdown_file.is_absolute():
        markdown_file = (PROJECT_ROOT / markdown_file).resolve()
    if not markdown_file.exists():
        print(f"ERROR: File not found: {markdown_file}")
        raise SystemExit(1)

    output_json = PROJECT_ROOT / "output" / f"{markdown_file.stem}.smoke.json"
    output_dir = PROJECT_ROOT / "output" / "smoke-fixed"
    output_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        (
            [
                sys.executable,
                "-m",
                "docstruct",
                "extract",
                str(markdown_file),
                "--output",
                str(output_json),
            ],
            "CLI extract",
        ),
        (
            [
                sys.executable,
                "-m",
                "docstruct",
                "fix",
                str(markdown_file),
                "--toc",
                str(output_json),
                "--output-dir",
                str(output_dir),
            ],
            "CLI fix",
        ),
        (
            [
                sys.executable,
                str(PROJECT_ROOT / "tools" / "run_pipeline.py"),
                str(markdown_file),
            ],
            "Single-file pipeline runner",
        ),
    ]

    for cmd, label in checks:
        code = run(cmd, label)
        if code != 0:
            print(f"\nSmoke test failed at: {label}")
            raise SystemExit(code)

    print("\nAll smoke-test scenarios passed.")


if __name__ == "__main__":
    main()

