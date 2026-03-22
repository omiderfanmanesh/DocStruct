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
from docstruct.application.pageindex_workflow import build_search_index
from docstruct.infrastructure.llm.factory import build_client
from docstruct.output_layout import ensure_output_layout


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(
    data_dir: Path,
    output_dir: Path,
    skip_extract: bool = False,
    skip_fix: bool = False,
    skip_index: bool = False,
    client=None,
    single_file: str | None = None,
) -> None:
    layout = ensure_output_layout(PROJECT_ROOT)
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
        toc_file = layout["toc"] / f"{md_file.stem}.json"
        fixed_output_dir = layout["fixed_markdown"]
        report_output_dir = layout["fix_reports"]
        pageindex_output_dir = layout["pageindex"]
        fixed_markdown_path = fixed_output_dir / md_file.name
        result_row: dict[str, object] = {"file": md_file.name}

        if not skip_extract:
            try:
                result = extract_toc(str(md_file), client)
                toc_file.parent.mkdir(parents=True, exist_ok=True)
                toc_file.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info("  Extracted TOC: %s entries", len(result.toc))
                result_row["toc_extraction"] = "SUCCESS"
            except Exception as exc:
                logger.error("  TOC extraction failed: %s", exc)
                result_row["toc_extraction"] = "FAILED"
                result_row["error"] = str(exc)
                results.append(result_row)
                continue
        elif not toc_file.exists():
            logger.error("  TOC file not found while extraction is skipped: %s", toc_file.name)
            result_row["toc_extraction"] = "FAILED"
            result_row["error"] = "TOC file missing"
            results.append(result_row)
            continue
        else:
            result_row["toc_extraction"] = "SKIPPED"

        if skip_fix:
            result_row["markdown_fix"] = "SKIPPED"
        else:
            try:
                fixed_output_dir.mkdir(parents=True, exist_ok=True)
                report_output_dir.mkdir(parents=True, exist_ok=True)
                report = fix_markdown(str(md_file), str(toc_file), str(fixed_output_dir), report_dir=str(report_output_dir))
                result_row["markdown_fix"] = "SUCCESS"
                result_row["corrections"] = report.lines_changed
                logger.info("  Markdown fixed; corrections: %s", report.lines_changed)
            except Exception as exc:
                logger.error("  Markdown fixing failed: %s", exc)
                result_row["markdown_fix"] = "FAILED"
                result_row["error"] = str(exc)
                results.append(result_row)
                continue

        if skip_index:
            result_row["document_search_index"] = "SKIPPED"
            results.append(result_row)
            continue

        if not fixed_markdown_path.exists():
            logger.info("  Search indexing skipped; fixed markdown not found: %s", fixed_markdown_path.name)
            result_row["document_search_index"] = "SKIPPED"
            results.append(result_row)
            continue

        try:
            index_output = pageindex_output_dir / f"{md_file.stem}.pageindex.json"
            build_search_index(
                str(fixed_markdown_path),
                str(index_output),
                extraction_json_path=str(toc_file) if toc_file.exists() else None,
            )
            result_row["document_search_index"] = "SUCCESS"
            logger.info("  Search index written: %s", index_output.name)
        except Exception as exc:
            logger.error("  Search indexing failed: %s", exc)
            result_row["document_search_index"] = "FAILED"
            result_row["error"] = str(exc)

        results.append(result_row)

    results_file = layout["runs"] / "pipeline_results.json"
    results_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Results saved to: %s", results_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full DocStruct pipeline for all documents or a single file")
    parser.add_argument("--file", default=None, help="Process a single markdown file (absolute or relative path)")
    parser.add_argument("--skip-extract", action="store_true", help="Skip TOC extraction and use existing JSON files")
    parser.add_argument("--skip-fix", action="store_true", help="Skip markdown fixing and only extract TOC")
    parser.add_argument("--skip-index", action="store_true", help="Skip PageIndex-backed search indexing")
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
            skip_index=args.skip_index,
            client=client,
            single_file=args.file,
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
