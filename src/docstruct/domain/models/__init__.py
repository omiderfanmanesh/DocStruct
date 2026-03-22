"""Domain models exposed as a single import surface."""

from docstruct.domain.models.correction import (
    CorrectionEntry,
    CorrectionReport,
    SourceLine,
    TOCEntry,
)
from docstruct.domain.models.heading import (
    DocumentMetadata,
    HeadingEntry,
    TOCBoundary,
)
from docstruct.domain.models.results import ExtractionResult, LogEntry

__all__ = [
    "CorrectionEntry",
    "CorrectionReport",
    "DocumentMetadata",
    "ExtractionResult",
    "HeadingEntry",
    "LogEntry",
    "SourceLine",
    "TOCBoundary",
    "TOCEntry",
]

