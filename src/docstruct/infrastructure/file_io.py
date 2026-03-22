"""Filesystem-backed I/O helpers."""

from __future__ import annotations

import json
from pathlib import Path

from docstruct.domain.models import CorrectionReport, SourceLine, TOCBoundary


class LocalFileReader:
    """Simple filesystem implementation of the file reader port."""

    def read_lines(self, path: str) -> list[str]:
        return read_markdown_file(path)


def read_markdown_file(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return handle.readlines()


def slice_toc_content(lines: list[str], boundary: TOCBoundary) -> str:
    return "".join(lines[boundary.start_line : boundary.end_line + 1])


def extract_pre_toc_content(lines: list[str], boundary: TOCBoundary) -> str:
    return "".join(
        line
        for line in lines[: boundary.start_line]
        if not line.strip().startswith("![image](")
    )


def parse_source_markdown(source_path: str) -> list[SourceLine]:
    with open(source_path, encoding="utf-8") as handle:
        return [
            SourceLine(line_number=line_number, raw_text=raw_text.rstrip("\n"))
            for line_number, raw_text in enumerate(handle, start=1)
        ]


def write_corrected_markdown(corrected_lines: list[SourceLine], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for line in corrected_lines:
            handle.write(line.raw_text + "\n")


def write_correction_report(report: CorrectionReport, output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, indent=2)

