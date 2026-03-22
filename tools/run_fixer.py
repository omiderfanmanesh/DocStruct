#!/usr/bin/env python
"""
Run the markdown fixer on all markdown files that have matching extracted TOC files.

This script:
1. Finds all markdown files in ./data
2. Looks for matching extracted TOC JSON in ./output
3. Runs the fixer (docstruct fix) for each pair
4. Generates corrected markdown + reports in output/fixed/

Note: Requires pre-extracted TOC files in output/ directory.
For extracting TOC from markdown, use: python -m docstruct extract <file.md> --output output/toc.json
"""

import os
import subprocess
import sys
from pathlib import Path
import json
import re

def find_markdown_files(data_dir: str = "data") -> list:
    """Find all MinerU-generated markdown files in data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    md_files = []
    for root, dirs, files in os.walk(data_path):
        for file in files:
            if file.endswith('.md') and 'MinerU_markdown' in file:
                md_files.append(os.path.join(root, file))

    return sorted(md_files)


def find_matching_toc(md_path: str, output_dir: str = "output") -> str:
    """Find matching TOC JSON file for a markdown file."""
    md_name = Path(md_path).stem

    # Look for exact match first
    exact_match = os.path.join(output_dir, f"{md_name}.json")
    if os.path.exists(exact_match):
        return exact_match

    # Look for partial match (first part of filename)
    for file in os.listdir(output_dir):
        if file.endswith('.json') and not file.endswith('_report.json'):
            if md_name.startswith(file.replace('.json', '')) or file.replace('.json', '') in md_name:
                return os.path.join(output_dir, file)

    return None


def run_command(cmd: list, description: str) -> bool:
    """Run a shell command and report status."""
    print(f"\n  > {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        if result.returncode != 0:
            print(f"    ERROR: Command failed (exit code {result.returncode})")
            if result.stderr:
                # Only show first few lines of error
                error_lines = result.stderr.split('\n')[:3]
                for line in error_lines:
                    if line.strip():
                        print(f"    {line.strip()[:100]}")
            return False
        if result.stdout:
            # Extract key info from stdout
            for line in result.stdout.split('\n'):
                if 'INFO:' in line or 'Lines changed' in line:
                    try:
                        print(f"    {line.strip()[:120]}")
                    except UnicodeEncodeError:
                        pass
        return True
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def process_markdown_file(md_path: str, toc_path: str) -> bool:
    """Process a single markdown file through the fixer."""
    md_path = os.path.normpath(md_path)
    toc_path = os.path.normpath(toc_path)
    md_name = Path(md_path).stem

    print(f"\n{'='*80}")
    print(f"File: {Path(md_path).name}")
    print(f"TOC:  {Path(toc_path).name}")
    print(f"{'='*80}")

    # Run fixer
    output_dir = "output/fixed"
    os.makedirs(output_dir, exist_ok=True)

    fix_cmd = [
        sys.executable,
        "-m", "docstruct", "fix",
        md_path,
        "--toc", toc_path,
        "--output-dir", output_dir
    ]

    if not run_command(fix_cmd, "Running markdown fixer"):
        return False

    # Report stats
    report_name = f"{md_name}_report.json"
    report_path = os.path.join(output_dir, report_name)

    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            print(f"\n  Results:")
            print(f"    Total lines:         {report.get('total_lines', 'N/A')}")
            print(f"    Lines changed:       {report.get('lines_changed', 'N/A')}")
            print(f"    Lines demoted:       {report.get('lines_demoted', 'N/A')}")
            unmatched = len(report.get('unmatched_toc_entries', []))
            print(f"    Unmatched TOC items: {unmatched}")
            print(f"    Output file:         output/fixed/{Path(md_path).name}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  Report generated (check {report_path})")

    return True


def main():
    """Main fixer runner."""
    print("\n" + "="*80)
    print("MinerU Markdown Fixer - Normalize Heading Levels")
    print("="*80)

    # Find all markdown files
    md_files = find_markdown_files("data")

    if not md_files:
        print("No MinerU markdown files found in ./data directory")
        sys.exit(1)

    print(f"\nFound {len(md_files)} markdown file(s)")

    # Find TOC files
    output_files = os.listdir("output") if os.path.exists("output") else []
    toc_files = [f for f in output_files if f.endswith('.json') and not f.endswith('_report.json')]

    if not toc_files:
        print("ERROR: No TOC JSON files found in ./output directory")
        print("Please extract TOC files first using:")
        print("  python -m docstruct extract <markdown_file> --output output/<name>.json")
        sys.exit(1)

    print(f"Found {len(toc_files)} TOC file(s) in output/\n")

    # Match and process files
    pairs = []
    skipped = []

    for md_path in md_files:
        toc_path = find_matching_toc(md_path)
        if toc_path:
            pairs.append((md_path, toc_path))
        else:
            skipped.append(md_path)

    if skipped:
        print(f"Skipping {len(skipped)} file(s) without matching TOC:")
        for f in skipped:
            print(f"  - {Path(f).name}")

    if not pairs:
        print("No markdown/TOC pairs found to process")
        sys.exit(1)

    print(f"Processing {len(pairs)} file pair(s):\n")

    # Process each pair
    successful = 0
    failed = 0

    for md_path, toc_path in pairs:
        try:
            if process_markdown_file(md_path, toc_path):
                successful += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n\nPipeline interrupted by user")
            break
        except Exception as e:
            print(f"\n  UNEXPECTED ERROR: {e}")
            failed += 1

    # Final summary
    print(f"\n\n" + "="*80)
    print("Fixer Complete")
    print("="*80)
    print(f"Successful: {successful}/{len(pairs)}")
    print(f"Failed:     {failed}/{len(pairs)}")
    print(f"\nOutput directory: {os.path.abspath('output/fixed')}")
    print(f"Report files:     output/fixed/*_report.json")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
