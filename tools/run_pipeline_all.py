#!/usr/bin/env python
"""Batch pipeline runner for DocStruct."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docstruct.application.extract_toc import extract_toc
from docstruct.application.fix_markdown import fix_markdown
from docstruct.infrastructure.llm.factory import build_client


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    data_dir: Path,
    output_dir: Path,
    skip_extract: bool = False,
    skip_fix: bool = False,
    client=None,
    single_file: str | None = None,
) -> None:
    if single_file:
        file_path = Path(single_file)
        if not file_path.is_absolute():
            file_path = data_dir / file_path.name
        md_files = [file_path] if file_path.exists() else []
    else:
        md_files = sorted(data_dir.glob("*.md"))

    if not md_files:
        logger.error("No markdown files found in %s", data_dir)
        return

    results = []
    for index, md_file in enumerate(md_files, start=1):
        logger.info("\n[%s/%s] Processing: %s", index, len(md_files), md_file.name)
        toc_file = output_dir / f"{md_file.stem}.json"

        if not skip_extract:
            try:
                result = extract_toc(str(md_file), client)
                toc_file.parent.mkdir(parents=True, exist_ok=True)
                toc_file.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info("  Extracted TOC: %s entries", len(result.toc))
            except Exception as exc:
                logger.error("  TOC extraction failed: %s", exc)
                results.append({"file": md_file.name, "toc_extraction": "FAILED", "error": str(exc)})
                continue
        elif not toc_file.exists():
            logger.error("  TOC file not found while extraction is skipped: %s", toc_file.name)
            results.append({"file": md_file.name, "toc_extraction": "FAILED", "error": "TOC file missing"})
            continue

        if skip_fix:
            results.append({"file": md_file.name, "toc_extraction": "SUCCESS", "markdown_fix": "SKIPPED"})
            continue

        try:
            fixed_output_dir = output_dir / "fixed"
            fixed_output_dir.mkdir(parents=True, exist_ok=True)
            report = fix_markdown(str(md_file), str(toc_file), str(fixed_output_dir))
            results.append({
                "file": md_file.name,
                "toc_extraction": "SUCCESS",
                "markdown_fix": "SUCCESS",
                "corrections": report.lines_changed,
            })
            logger.info("  Markdown fixed; corrections: %s", report.lines_changed)
        except Exception as exc:
            logger.error("  Markdown fixing failed: %s", exc)
            results.append({
                "file": md_file.name,
                "toc_extraction": "SUCCESS",
                "markdown_fix": "FAILED",
                "error": str(exc),
            })

    results_file = output_dir / "pipeline_results.json"
    results_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Results saved to: %s", results_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full DocStruct pipeline for all documents or a single file")
    parser.add_argument("--file", default=None, help="Process a single markdown file (absolute or relative path)")
    parser.add_argument("--skip-extract", action="store_true", help="Skip TOC extraction and use existing JSON files")
    parser.add_argument("--skip-fix", action="store_true", help="Skip markdown fixing and only extract TOC")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    output_dir = project_root / "output"

    client = None
    if not args.skip_extract:
        try:
            client = build_client()
        except Exception as exc:
            logger.error("Could not initialize LLM client: %s", exc)
            raise SystemExit(1)

    try:
        run_pipeline(
            data_dir,
            output_dir,
            skip_extract=args.skip_extract,
            skip_fix=args.skip_fix,
            client=client,
            single_file=args.file,
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
