#!/usr/bin/env python
"""
Batch pipeline runner: Extract TOC and fix markdown for all documents in /data.

Usage:
    python scripts/run_pipeline_all.py [--skip-extract] [--skip-fix]
    python scripts/run_pipeline_all.py --file <markdown_file> [--skip-extract] [--skip-fix]

Options:
    --file <path>     Process a single markdown file (absolute or relative path)
    --skip-extract    Skip TOC extraction (use existing JSON files)
    --skip-fix        Skip markdown fixing (only extract TOC)
"""

import json
import sys
from pathlib import Path
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from docstruct.pipeline.extractor import extract_toc
from docstruct.pipeline.md_fixer import fix_markdown
from docstruct.providers.factory import build_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_pipeline(
    data_dir: Path,
    output_dir: Path,
    skip_extract: bool = False,
    skip_fix: bool = False,
    client=None,
    single_file: str = None,
):
    """
    Run full pipeline for markdown files in data_dir.

    Args:
        data_dir: Directory containing markdown files
        output_dir: Output directory for TOC and fixed markdown
        skip_extract: Skip TOC extraction if True
        skip_fix: Skip markdown fixing if True
        client: LLM client for TOC extraction (required unless skip_extract)
        single_file: If provided, only process this specific file
    """
    # Find markdown files
    if single_file:
        file_path = Path(single_file)
        if not file_path.is_absolute():
            file_path = data_dir / file_path.name
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return
        md_files = [file_path]
    else:
        md_files = sorted(data_dir.glob("*.md"))

    if not md_files:
        logger.error(f"No markdown files found in {data_dir}")
        return

    logger.info(f"Found {len(md_files)} markdown file(s) to process")

    results = []

    for i, md_file in enumerate(md_files, 1):
        logger.info(f"\n[{i}/{len(md_files)}] Processing: {md_file.name}")

        # Step 1: Extract TOC
        toc_file = output_dir / f"{md_file.stem}.json"

        if skip_extract and toc_file.exists():
            logger.info(f"  ✓ TOC exists (skipped extraction): {toc_file.name}")
        elif skip_extract and not toc_file.exists():
            logger.error(f"  ✗ TOC file not found (--skip-extract set): {toc_file.name}")
            results.append({
                'file': md_file.name,
                'toc_extraction': 'FAILED',
                'error': 'TOC file not found and extraction skipped'
            })
            continue
        else:
            try:
                logger.info(f"  → Extracting TOC...")
                result = extract_toc(str(md_file), client)

                # Write TOC
                toc_file.parent.mkdir(parents=True, exist_ok=True)
                with open(toc_file, 'w', encoding='utf-8') as f:
                    json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

                logger.info(f"  ✓ TOC extracted: {len(result.toc)} entries")
                logger.info(f"    Saved to: {toc_file.name}")

            except Exception as e:
                logger.error(f"  ✗ TOC extraction failed: {e}")
                results.append({
                    'file': md_file.name,
                    'toc_extraction': 'FAILED',
                    'error': str(e)
                })
                continue

        # Step 2: Fix markdown
        if not skip_fix:
            if not toc_file.exists():
                logger.error(f"  ✗ TOC file not found: {toc_file.name}")
                results.append({
                    'file': md_file.name,
                    'markdown_fix': 'FAILED',
                    'error': 'TOC file not found'
                })
                continue

            try:
                logger.info(f"  → Fixing markdown...")
                fixed_output_dir = output_dir / "fixed"
                fixed_output_dir.mkdir(parents=True, exist_ok=True)

                report = fix_markdown(
                    str(md_file),
                    str(toc_file),
                    str(fixed_output_dir),
                )

                logger.info(f"  ✓ Markdown fixed")
                report_dict = report.to_dict() if hasattr(report, 'to_dict') else report
                lines_changed = report_dict.get('lines_changed', 0)
                logger.info(f"    Lines corrected: {lines_changed}")
                logger.info(f"    Output: {fixed_output_dir.name}/{md_file.stem}*.md")

                results.append({
                    'file': md_file.name,
                    'toc_extraction': 'SUCCESS',
                    'markdown_fix': 'SUCCESS',
                    'corrections': lines_changed
                })

            except Exception as e:
                logger.error(f"  ✗ Markdown fixing failed: {e}")
                results.append({
                    'file': md_file.name,
                    'toc_extraction': 'SUCCESS',
                    'markdown_fix': 'FAILED',
                    'error': str(e)
                })
        else:
            results.append({
                'file': md_file.name,
                'toc_extraction': 'SUCCESS',
                'markdown_fix': 'SKIPPED'
            })

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 80)

    success_count = sum(1 for r in results if r.get('toc_extraction') == 'SUCCESS')
    fix_count = sum(1 for r in results if r.get('markdown_fix') == 'SUCCESS')

    for r in results:
        status = "✓" if r.get('markdown_fix') == 'SUCCESS' else "✗"
        logger.info(f"{status} {r['file']}")
        if 'error' in r:
            logger.info(f"  Error: {r['error']}")
        if 'corrections' in r:
            logger.info(f"  Corrections: {r['corrections']}")

    logger.info("-" * 80)
    logger.info(f"TOC Extraction: {success_count}/{len(md_files)} successful")
    if not skip_fix:
        logger.info(f"Markdown Fixing: {fix_count}/{len(md_files)} successful")
    logger.info("=" * 80)

    # Save results to JSON
    results_file = output_dir / f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to: {results_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description='Run full pipeline (TOC extraction + markdown fixing) for all documents or a single file'
    )
    parser.add_argument(
        '--file',
        default=None,
        help='Process a single markdown file (absolute or relative path)'
    )
    parser.add_argument(
        '--skip-extract',
        action='store_true',
        help='Skip TOC extraction (use existing JSON files)'
    )
    parser.add_argument(
        '--skip-fix',
        action='store_true',
        help='Skip markdown fixing (only extract TOC)'
    )

    args = parser.parse_args()

    # Setup paths
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    output_dir = project_root / "output"

    # Build LLM client (required for TOC extraction unless skipped)
    client = None
    if not args.skip_extract:
        try:
            logger.info("Building LLM client for TOC extraction...")
            client = build_client()
            logger.info("✓ LLM client ready for TOC extraction")
        except Exception as e:
            logger.error(f"Could not initialize LLM client: {e}")
            sys.exit(1)
    else:
        logger.info("Skipping TOC extraction (using existing JSON files)")

    # Run pipeline
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
        logger.info("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
