"""Document reading and slicing utilities."""
from __future__ import annotations

from docstruct.models.document import TOCBoundary


def read_markdown_file(path: str) -> list[str]:
    """Read a markdown file and return its lines."""
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def slice_toc_content(lines: list[str], boundary: TOCBoundary) -> str:
    """Return the raw text of the TOC section."""
    return "".join(lines[boundary.start_line : boundary.end_line + 1])


def extract_pre_toc_content(lines: list[str], boundary: TOCBoundary) -> str:
    """Return lines before the TOC start, skipping image lines."""
    pre = [
        line for line in lines[: boundary.start_line]
        if not line.strip().startswith("![image](")
    ]
    return "".join(pre)
