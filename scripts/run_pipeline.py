#!/usr/bin/env python
"""
Run the full MinerU pipeline on all markdown files in ./data directory.

Pipeline steps:
1. Extract TOC from each markdown file (docstruct extract)
2. Fix heading levels using extracted TOC (docstruct fix)
3. Generate reports and corrected markdown in output/fixed/
"""

import os
import subprocess
import sys
from pathlib import Path
import json

def find_markdown_files(data_dir: str = "data") -> list:
    """Find all MinerU-generated markdown files in data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    md_files = []
    for root, dirs, files in os.walk(data_path):
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))

    return sorted(md_files)


def run_command(cmd: list, description: str) -> bool:
    """Run a shell command and report status."""
    print(f"\n  > {description}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        if result.returncode != 0:
            print(f"    ERROR: Command failed")
            if result.stderr:
                print(f"    {result.stderr[:200]}")
            return False
        if result.stdout:
            # Extract key info from stdout
            for line in result.stdout.split('\n'):
                if 'INFO:' in line or 'Lines changed' in line:
                    try:
                        print(f"    {line.strip()}")
                    except UnicodeEncodeError:
                        print(f"    (Output contains Unicode, check file directly)")
        return True
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def process_markdown_file(md_path: str) -> bool:
    """Process a single markdown file through the pipeline."""
    md_path = os.path.normpath(md_path)
    md_name = Path(md_path).stem

    print(f"\n{'='*80}")
    print(f"Processing: {md_path}")
    print(f"{'='*80}")

    # Step 1: Extract TOC
    output_json = f"output/{md_name}.json"
    os.makedirs("output", exist_ok=True)

    extract_cmd = [
        sys.executable,
        "-m", "docstruct", "extract",
        md_path,
        "--output", output_json
    ]

    if not run_command(extract_cmd, "Step 1: Extracting TOC from markdown"):
        return False

    if not os.path.exists(output_json):
        print(f"  ERROR: TOC file not created: {output_json}")
        return False

    # Step 2: Fix heading levels
    output_dir = "output/fixed"
    os.makedirs(output_dir, exist_ok=True)

    fix_cmd = [
        sys.executable,
        "-m", "docstruct", "fix",
        md_path,
        "--toc", output_json,
        "--output-dir", output_dir
    ]

    if not run_command(fix_cmd, "Step 2: Fixing heading levels"):
        return False

    # Report stats
    report_name = f"{md_name}_report.json"
    report_path = os.path.join(output_dir, report_name)

    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            print(f"\n  Summary:")
            print(f"    - Total lines: {report.get('total_lines', 'N/A')}")
            print(f"    - Lines changed: {report.get('lines_changed', 'N/A')}")
            print(f"    - Lines demoted: {report.get('lines_demoted', 'N/A')}")
            print(f"    - Unmatched TOC entries: {len(report.get('unmatched_toc_entries', []))}")
            print(f"    - Output: {output_dir}/{Path(md_path).name}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  (Report generated but could not parse JSON)")

    return True


def main():
    """Main pipeline runner. Pass a file path as argument to process a single file."""
    print("\n" + "="*80)
    print("MinerU Pipeline Runner - Extract TOC & Fix Heading Levels")
    print("="*80)

    # If a path is given as argument, process that file directly
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if os.path.isfile(target):
            md_files = [target]
        else:
            print(f"ERROR: File not found: {target}")
            sys.exit(1)
    else:
        # Find all markdown files in data/
        md_files = find_markdown_files("data")

    if not md_files:
        print("No MinerU markdown files found in ./data directory")
        sys.exit(1)

    print(f"\nFound {len(md_files)} markdown file(s) to process:")
    for i, f in enumerate(md_files, 1):
        print(f"  {i}. {f}")

    # Process each file
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
        except Exception as e:
            print(f"\n  UNEXPECTED ERROR: {e}")
            failed += 1

    # Final summary
    print(f"\n\n" + "="*80)
    print("Pipeline Complete")
    print("="*80)
    print(f"Successful: {successful}/{len(md_files)}")
    print(f"Failed: {failed}/{len(md_files)}")
    print(f"Output directory: {os.path.abspath('output/fixed')}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
