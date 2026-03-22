#!/usr/bin/env python
"""Run the markdown fixer for files that already have extracted TOC JSON output."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"


def find_markdown_files(data_dir: str = "data") -> list[str]:
    data_path = PROJECT_ROOT / data_dir
    if not data_path.exists():
        print(f"ERROR: Data directory not found: {data_path}")
        raise SystemExit(1)
    return sorted(str(path) for path in data_path.glob("*.md"))


def find_matching_toc(md_path: str, output_dir: str = "output") -> str | None:
    output_path = PROJECT_ROOT / output_dir
    md_name = Path(md_path).stem
    exact_match = output_path / f"{md_name}.json"
    if exact_match.exists():
        return str(exact_match)
    for file in output_path.glob("*.json"):
        if file.name.endswith("_report.json"):
            continue
        stem = file.stem
        if md_name.startswith(stem) or stem in md_name:
            return str(file)
    return None


def run_command(cmd: list[str], description: str) -> bool:
    print(f"\n  > {description}")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", env=env)
        if result.returncode != 0:
            print(f"    ERROR: Command failed (exit code {result.returncode})")
            for line in result.stderr.splitlines()[:3]:
                if line.strip():
                    print(f"    {line.strip()[:100]}")
            return False
        return True
    except Exception as exc:
        print(f"    ERROR: {exc}")
        return False


def process_markdown_file(md_path: str, toc_path: str) -> bool:
    print(f"\n{'=' * 80}")
    print(f"File: {Path(md_path).name}")
    print(f"TOC:  {Path(toc_path).name}")
    print(f"{'=' * 80}")

    output_dir = PROJECT_ROOT / "output" / "fixed"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not run_command([sys.executable, "-m", "docstruct", "fix", md_path, "--toc", toc_path, "--output-dir", str(output_dir)], "Running markdown fixer"):
        return False

    report_path = output_dir / f"{Path(md_path).stem}_report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            print("\n  Results:")
            print(f"    Total lines:         {report.get('total_lines', 'N/A')}")
            print(f"    Lines changed:       {report.get('lines_changed', 'N/A')}")
            print(f"    Lines demoted:       {report.get('lines_demoted', 'N/A')}")
            print(f"    Unmatched TOC items: {len(report.get('unmatched_toc_entries', []))}")
            print(f"    Output file:         output/fixed/{Path(md_path).name}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  Report generated (check {report_path})")
    return True


def main() -> None:
    print("\n" + "=" * 80)
    print("DocStruct Markdown Fixer")
    print("=" * 80)

    md_files = find_markdown_files("data")
    if not md_files:
        print("No markdown files found in ./data directory")
        raise SystemExit(1)

    pairs: list[tuple[str, str]] = []
    skipped: list[str] = []
    for md_path in md_files:
        toc_path = find_matching_toc(md_path)
        if toc_path:
            pairs.append((md_path, toc_path))
        else:
            skipped.append(md_path)

    if skipped:
        print(f"Skipping {len(skipped)} file(s) without matching TOC:")
        for path in skipped:
            print(f"  - {Path(path).name}")

    if not pairs:
        print("No markdown/TOC pairs found to process")
        raise SystemExit(1)

    successful = 0
    failed = 0
    for md_path, toc_path in pairs:
        try:
            if process_markdown_file(md_path, toc_path):
                successful += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n\nFixer interrupted by user")
            break
        except Exception as exc:
            print(f"\n  UNEXPECTED ERROR: {exc}")
            failed += 1

    print(f"\n\n{'=' * 80}")
    print("Fixer Complete")
    print("=" * 80)
    print(f"Successful: {successful}/{len(pairs)}")
    print(f"Failed:     {failed}/{len(pairs)}")
    print(f"Output directory: {PROJECT_ROOT / 'output' / 'fixed'}")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
