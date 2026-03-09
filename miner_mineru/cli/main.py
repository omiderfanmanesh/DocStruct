"""CLI entry point for the TOC extraction agent.

Usage:
    python -m miner_mineru <markdown_file_path> [--output <path>]

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
    parser = argparse.ArgumentParser(description="MinerU TOC extraction and fixing tools")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # extract subcommand
    extract_parser = subparsers.add_parser("extract", help="Extract TOC from markdown (default)")
    extract_parser.add_argument("markdown_file", help="Path to MinerU-generated markdown file")
    extract_parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)", default=None)

    # fix subcommand
    fix_parser = subparsers.add_parser("fix", help="Fix markdown heading levels using extracted TOC")
    fix_parser.add_argument("markdown_file", help="Path to source markdown file")
    fix_parser.add_argument("--toc", required=True, help="Path to step 1 output JSON (contains toc array)")
    fix_parser.add_argument("--output-dir", "-o", required=True, help="Output directory for corrected markdown + report")
    fix_parser.add_argument(
        "--inference-model",
        default=None,
        help="Optional separate LLM model for heading inference (if not provided, uses same model as TOC extraction)"
    )

    # load subcommand
    load_parser = subparsers.add_parser("load", help="Load and clean MinerU JSON extraction")
    load_parser.add_argument("json_file", help="Path to MinerU JSON extraction file")
    load_parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)", default=None)

    args = parser.parse_args()

    # Handle load subcommand (clean MinerU JSON)
    if args.command == "load":
        from miner_mineru.pipeline.json_loader import load_mineru_json, save_cleaned_json
        try:
            print(f"INFO: Loading MinerU JSON: {args.json_file}", file=sys.stderr)
            doc = load_mineru_json(args.json_file)
            print(f"INFO: Loaded {len(doc.pages)} pages, {len(doc.get_all_blocks())} blocks", file=sys.stderr)

            output_json = json.dumps(doc.to_dict(), indent=2, ensure_ascii=False)

            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_json)
                print(f"INFO: Cleaned JSON saved to {args.output}", file=sys.stderr)
            else:
                print(output_json)

            sys.exit(0)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle fix subcommand
    if args.command == "fix":
        from miner_mineru.pipeline.md_fixer import fix_markdown
        from miner_mineru.providers.factory import build_client
        try:
            print(f"INFO: Fixing markdown: {args.markdown_file}", file=sys.stderr)

            # Build main LLM client
            client = build_client()

            # Build optional separate inference client if specified
            inference_client = None
            if args.inference_model:
                import os
                original_model = os.getenv("LLM_MODEL")
                try:
                    os.environ["LLM_MODEL"] = args.inference_model
                    inference_client = build_client()
                    print(f"INFO: Using separate model for heading inference: {args.inference_model}", file=sys.stderr)
                finally:
                    if original_model:
                        os.environ["LLM_MODEL"] = original_model
                    else:
                        os.environ.pop("LLM_MODEL", None)

            report = fix_markdown(args.markdown_file, args.toc, args.output_dir, client=client, inference_client=inference_client)
            print(f"INFO: Lines changed: {report.lines_changed}, Lines demoted: {report.lines_demoted}", file=sys.stderr)
            print(f"INFO: Output written to {args.output_dir}", file=sys.stderr)
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
            # If no subcommand, treat first arg as markdown file (backward compat)
            if len(sys.argv) < 2:
                parser.print_help()
                sys.exit(0)
            args.markdown_file = sys.argv[1]
            args.output = sys.argv[3] if len(sys.argv) > 2 and sys.argv[2] in ['-o', '--output'] else None

        from miner_mineru.providers.factory import build_client
        client = build_client()

        print(f"INFO: Reading file: {args.markdown_file}", file=sys.stderr)

        try:
            from miner_mineru.pipeline.extractor import extract_toc
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
            print(f"INFO: Output written to {args.output}", file=sys.stderr)
        else:
            print(output_json)

        print("INFO: Extraction complete.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
