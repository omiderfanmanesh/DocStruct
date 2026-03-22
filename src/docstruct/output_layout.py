"""Shared output-directory layout for pipeline artifacts.

Pass the project root into :func:`ensure_output_layout`.
"""

from __future__ import annotations

from pathlib import Path
import re


OUTPUT_ROOT = Path("output")
RUNS_DIR = OUTPUT_ROOT / "00_runs"
TOC_DIR = OUTPUT_ROOT / "01_toc"
FIXED_MARKDOWN_DIR = OUTPUT_ROOT / "02_fixed_markdown"
FIX_REPORTS_DIR = OUTPUT_ROOT / "02_fix_reports"
PAGEINDEX_DIR = OUTPUT_ROOT / "03_pageindex"
ANSWERS_DIR = OUTPUT_ROOT / "04_answers"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def ensure_output_layout(project_root: Path) -> dict[str, Path]:
    layout = {
        "root": project_root / OUTPUT_ROOT,
        "runs": project_root / RUNS_DIR,
        "toc": project_root / TOC_DIR,
        "fixed_markdown": project_root / FIXED_MARKDOWN_DIR,
        "fix_reports": project_root / FIX_REPORTS_DIR,
        "pageindex": project_root / PAGEINDEX_DIR,
        "answers": project_root / ANSWERS_DIR,
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def slugify(text: str, *, fallback: str = "query", max_length: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    if not slug:
        slug = fallback
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug
