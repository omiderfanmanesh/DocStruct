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
from docstruct.domain.models.search import (
    SearchAnswer,
    SearchCitation,
    SearchDocumentIndex,
    SearchSelectionDecision,
)

__all__ = [
    "CorrectionEntry",
    "CorrectionReport",
    "DocumentMetadata",
    "ExtractionResult",
    "HeadingEntry",
    "LogEntry",
    "SearchAnswer",
    "SearchCitation",
    "SearchDocumentIndex",
    "SearchSelectionDecision",
    "SourceLine",
    "TOCBoundary",
    "TOCEntry",
]

