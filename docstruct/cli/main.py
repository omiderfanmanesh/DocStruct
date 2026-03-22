"""CLI entry point for the TOC extraction agent.

Usage:
    python -m docstruct <markdown_file_path> [--output <path>]

Exit codes:
    0 - success
    1 - file not found or unreadable
    2 - no TOC section detected
    3 - LLM API error

Provider is selected via LLM_PROVIDER in .env (or environment):
    LLM_PROVIDER=azure      → Azure OpenAI (gpt-4.1-mini by default)
    LLM_PROVIDER=anthropic  → Anthropic Claude (default)
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="DocStruct TOC extraction and fixing tools")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # extract subcommand
    extract_parser = subparsers.add_parser("extract", help="Extract TOC from markdown (default)")
    extract_parser.add_argument("markdown_file", help="Path to markdown file")
    extract_parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)", default=None)

    # fix subcommand
    fix_parser = subparsers.add_parser("fix", help="Fix markdown heading levels using extracted TOC")
    fix_parser.add_argument("markdown_file", help="Path to source markdown file")
    fix_parser.add_argument("--toc", required=True, help="Path to step 1 output JSON (contains toc array)")
    fix_parser.add_argument("--output-dir", "-o", required=True, help="Output directory for corrected markdown + report")

    args = parser.parse_args()

    # Handle fix subcommand
    if args.command == "fix":
        from docstruct.pipeline.md_fixer import fix_markdown
        try:
            print(f"Fixing: {args.markdown_file}", file=sys.stderr)
            report = fix_markdown(args.markdown_file, args.toc, args.output_dir)
            unmatched = len(report.unmatched_toc_entries)
            total_toc = report.lines_changed + report.lines_demoted + unmatched
            print(
                f"  Changed {report.lines_changed} headings, demoted {report.lines_demoted}"
                + (f", {unmatched} TOC entries unmatched" if unmatched else ""),
                file=sys.stderr,
            )
            print(f"  Output: {args.output_dir}", file=sys.stderr)
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            sys.exit(0)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Default: extract subcommand (or no subcommand specified)
    if args.command == "extract" or args.command is None:
        if args.command is None:
            if len(sys.argv) < 2:
                parser.print_help()
                sys.exit(0)
            args.markdown_file = sys.argv[1]
            args.output = sys.argv[3] if len(sys.argv) > 2 and sys.argv[2] in ['-o', '--output'] else None

        from docstruct.providers.factory import build_client
        client = build_client()

        print(f"Extracting: {args.markdown_file}", file=sys.stderr)

        try:
            from docstruct.pipeline.extractor import extract_toc
            result = extract_toc(args.markdown_file, client)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"ERROR: LLM API error: {e}", file=sys.stderr)
            sys.exit(3)

        output_json = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"  Output: {args.output}", file=sys.stderr)
        else:
            print(output_json)

        sys.exit(0)


if __name__ == "__main__":
    main()
