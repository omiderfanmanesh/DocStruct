#!/usr/bin/env python
"""Run the full DocStruct pipeline on markdown files in ./data."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docstruct.output_layout import FIXED_MARKDOWN_DIR, FIX_REPORTS_DIR, TOC_DIR


def find_markdown_files(data_dir: str = "data") -> list[str]:
    data_path = PROJECT_ROOT / data_dir
    if not data_path.exists():
        print(f"ERROR: Data directory not found: {data_path}")
        raise SystemExit(1)
    return sorted(str(path) for path in data_path.glob("*.md"))


def run_command(cmd: list[str], description: str) -> bool:
    print(f"\n  > {description}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=None, text=True, errors="replace", env=env)
        if result.returncode != 0:
            print(f"    ERROR: Command failed (exit {result.returncode})")
            return False
        return True
    except Exception as exc:
        print(f"    ERROR: {exc}")
        return False


def process_markdown_file(md_path: str) -> bool:
    md_path = os.path.normpath(md_path)
    md_name = Path(md_path).stem
    print(f"\n{'=' * 80}")
    print(f"Processing: {md_path}")
    print(f"{'=' * 80}")

    output_json = str(PROJECT_ROOT / TOC_DIR / f"{md_name}.json")
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    if not run_command([sys.executable, "-m", "docstruct", "extract", md_path, "--output", output_json], "Step 1: Extracting TOC from markdown"):
        return False

    output_dir = str(PROJECT_ROOT / FIXED_MARKDOWN_DIR)
    report_dir = str(PROJECT_ROOT / FIX_REPORTS_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    if not run_command([sys.executable, "-m", "docstruct", "fix", md_path, "--toc", output_json, "--output-dir", output_dir, "--report-dir", report_dir], "Step 2: Fixing heading levels"):
        return False

    report_path = Path(report_dir) / f"{md_name}_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            print("\n  Summary:")
            print(f"    - Total lines: {report.get('total_lines', 'N/A')}")
            print(f"    - Lines changed: {report.get('lines_changed', 'N/A')}")
            print(f"    - Lines demoted: {report.get('lines_demoted', 'N/A')}")
            print(f"    - Unmatched TOC entries: {len(report.get('unmatched_toc_entries', []))}")
            print(f"    - Markdown: {FIXED_MARKDOWN_DIR / Path(md_path).name}")
            print(f"    - Report: {FIX_REPORTS_DIR / report_path.name}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("  (Report generated but could not parse JSON)")
    return True


def main() -> None:
    print("\n" + "=" * 80)
    print("DocStruct Pipeline Runner")
    print("=" * 80)

    md_files = [sys.argv[1]] if len(sys.argv) > 1 else find_markdown_files("data")
    if not md_files:
        print("No markdown files found in ./data directory")
        raise SystemExit(1)

    successful = 0
    failed = 0
    for md_path in md_files:
        try:
            if process_markdown_file(md_path):
                successful += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n\nPipeline interrupted by user")
            break
        except Exception as exc:
            print(f"\n  UNEXPECTED ERROR: {exc}")
            failed += 1

    print(f"\n\n{'=' * 80}")
    print("Pipeline Complete")
    print("=" * 80)
    print(f"Successful: {successful}/{len(md_files)}")
    print(f"Failed: {failed}/{len(md_files)}")
    print(f"Markdown output: {PROJECT_ROOT / FIXED_MARKDOWN_DIR}")
    print(f"Report output:   {PROJECT_ROOT / FIX_REPORTS_DIR}")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
