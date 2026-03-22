"""DocStruct public API."""

from docstruct.application.agents import (
    AgentChain,
    AgentResult,
    BaseAgent,
    BoundaryAgent,
    ClassifierAgent,
    MetadataAgent,
    SummaryAgent,
)
from docstruct.config import AgentConfig, ProcessingConfig
from docstruct.domain.exceptions import DocStructError
from docstruct.domain.models import (
    DocumentMetadata,
    ExtractionResult,
    HeadingEntry,
    LogEntry,
    SearchAnswer,
    SearchCitation,
    SearchDocumentIndex,
    TOCBoundary,
)

__all__ = [
    "AgentChain",
    "AgentConfig",
    "AgentResult",
    "BaseAgent",
    "BoundaryAgent",
    "ClassifierAgent",
    "DocStructError",
    "DocumentMetadata",
    "ExtractionResult",
    "HeadingEntry",
    "LogEntry",
    "MetadataAgent",
    "ProcessingConfig",
    "SearchAnswer",
    "SearchCitation",
    "SearchDocumentIndex",
    "SummaryAgent",
    "TOCBoundary",
]

__version__ = "0.1.0"

