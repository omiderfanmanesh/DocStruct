"""Markdown-correction domain entities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class TOCEntry:
    title: str
    kind: str
    depth: int
    numbering: str | None = None
    separator: str | None = None
    pattern: str | None = None
    page: int | None = None
    confidence: float = 1.0

    def build_pattern(self) -> str | None:
        if self.numbering and self.separator is not None and self.title:
            return f"{self.numbering}{self.separator}{self.title}"
        if self.numbering and self.title:
            return f"{self.numbering} {self.title}"
        return self.title or None

    def heading_pattern(self) -> str | None:
        return self.pattern or self.build_pattern()

    def search_patterns(self) -> list[str]:
        canonical = self.heading_pattern()
        if self.pattern or self.separator is not None or not self.numbering or not self.title:
            return [canonical] if canonical else []
        return [
            f"{self.numbering} - {self.title}",
            f"{self.numbering} – {self.title}",
            f"{self.numbering} -{self.title}",
            f"{self.numbering}: {self.title}",
            f"{self.numbering} {self.title}",
        ]

    def needle(self) -> str | None:
        return self.heading_pattern()


@dataclass
class SourceLine:
    line_number: int
    raw_text: str
    heading_level: int | None = None
    stripped_text: str | None = None

    def __post_init__(self) -> None:
        if self.stripped_text is None:
            self.stripped_text = self.raw_text.lstrip("#").strip()
            if self.raw_text.startswith("#"):
                self.heading_level = len(self.raw_text) - len(self.raw_text.lstrip("#"))


@dataclass
class CorrectionEntry:
    line_number: int
    old_level: int | None
    new_level: int | None
    matched_toc_title: str | None
    match_method: str


@dataclass
class CorrectionReport:
    source_file: str
    output_file: str
    total_lines: int
    lines_changed: int
    lines_demoted: int
    unmatched_toc_entries: list[str] = field(default_factory=list)
    corrections: list[CorrectionEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "output_file": self.output_file,
            "total_lines": self.total_lines,
            "lines_changed": self.lines_changed,
            "lines_demoted": self.lines_demoted,
            "unmatched_toc_entries": self.unmatched_toc_entries,
            "corrections": [asdict(correction) for correction in self.corrections],
        }
