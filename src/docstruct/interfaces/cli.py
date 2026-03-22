"""CLI entry point for DocStruct."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from docstruct.application.extract_toc import extract_toc
from docstruct.application.fix_markdown import fix_markdown
from docstruct.application.pageindex_workflow import (
    answer_question,
    build_search_indexes,
)
from docstruct.infrastructure.llm.factory import build_client
from docstruct.output_layout import FIXED_MARKDOWN_DIR, FIX_REPORTS_DIR, PAGEINDEX_DIR, TOC_DIR


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="DocStruct TOC extraction and fixing tools")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    extract_parser = subparsers.add_parser("extract", help="Extract TOC from markdown (default)")
    extract_parser.add_argument("markdown_file", help="Path to markdown file")
    extract_parser.add_argument("--output", "-o", default=None, help="Output JSON file path (default: stdout)")

    fix_parser = subparsers.add_parser("fix", help="Fix markdown heading levels using extracted TOC")
    fix_parser.add_argument("markdown_file", help="Path to source markdown file")
    fix_parser.add_argument("--toc", required=True, help="Path to extraction JSON (contains toc array)")
    fix_parser.add_argument("--output-dir", "-o", default=str(FIXED_MARKDOWN_DIR), help="Output directory for corrected markdown")
    fix_parser.add_argument("--report-dir", default=str(FIX_REPORTS_DIR), help="Output directory for correction reports")

    index_parser = subparsers.add_parser("index", help="Build PageIndex-backed search indexes from fixed markdown")
    index_parser.add_argument("path", nargs="?", default=str(FIXED_MARKDOWN_DIR), help="Markdown file or directory to index")
    index_parser.add_argument("--output-dir", "-o", default=str(PAGEINDEX_DIR), help="Directory for generated search indexes")
    index_parser.add_argument("--toc-dir", default=str(TOC_DIR), help="Directory containing extraction JSON files for metadata/summary")

    ask_parser = subparsers.add_parser("ask", help="Ask a question across PageIndex-backed document indexes")
    ask_parser.add_argument("question", help="Question to answer from indexed documents")
    ask_parser.add_argument("--index-dir", "-i", default=str(PAGEINDEX_DIR), help="Directory containing generated search indexes")

    args = parser.parse_args()

    if args.command == "index":
        target = Path(args.path)
        markdown_files = [target] if target.is_file() else sorted(target.glob("*.md"))
        if not markdown_files:
            print(f"ERROR: No markdown files found in {target}", file=sys.stderr)
            raise SystemExit(1)
        print(f"Indexing {len(markdown_files)} markdown file(s) with PageIndex...", file=sys.stderr)
        try:
            indexes = build_search_indexes(
                [str(markdown_file) for markdown_file in markdown_files],
                args.output_dir,
                extraction_dir=args.toc_dir,
            )
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1)
        print(f"  Output: {args.output_dir}", file=sys.stderr)
        print(json.dumps([index.to_dict() for index in indexes], indent=2, ensure_ascii=False))
        raise SystemExit(0)

    if args.command == "ask":
        client = build_client()
        print(f"Searching indexed documents in {args.index_dir}...", file=sys.stderr)
        try:
            result = answer_question(args.question, args.index_dir, client)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        raise SystemExit(0)

    if args.command == "fix":
        try:
            print(f"Fixing: {args.markdown_file}", file=sys.stderr)
            report = fix_markdown(args.markdown_file, args.toc, args.output_dir, report_dir=args.report_dir)
            unmatched = len(report.unmatched_toc_entries)
            print(
                f"  Changed {report.lines_changed} headings, demoted {report.lines_demoted}"
                + (f", {unmatched} TOC entries unmatched" if unmatched else ""),
                file=sys.stderr,
            )
            print(f"  Output: {args.output_dir}", file=sys.stderr)
            print(f"  Report: {args.report_dir}", file=sys.stderr)
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            raise SystemExit(0)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1)

    if args.command == "extract" or args.command is None:
        if args.command is None:
            if len(sys.argv) < 2:
                parser.print_help()
                raise SystemExit(0)
            args.markdown_file = sys.argv[1]
            args.output = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] in {"-o", "--output"} else None

        client = build_client()
        print(f"Extracting: {args.markdown_file}", file=sys.stderr)
        try:
            result = extract_toc(args.markdown_file, client)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
        except Exception as exc:
            print(f"ERROR: LLM API error: {exc}", file=sys.stderr)
            raise SystemExit(3)

        output_json = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(output_json)
            print(f"  Output: {args.output}", file=sys.stderr)
        else:
            print(output_json)
        raise SystemExit(0)
