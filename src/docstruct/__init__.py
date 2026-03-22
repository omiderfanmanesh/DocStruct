"""docstruct — LLM-based TOC extraction and markdown fixing pipeline."""

from docstruct.agents import (
    BaseAgent,
    AgentResult,
    AgentChain,
    BoundaryAgent,
    ClassifierAgent,
    SummaryAgent,
    MetadataAgent,
)
from docstruct.models import (
    HeadingEntry,
    TOCBoundary,
    DocumentMetadata,
    ExtractionResult,
    LogEntry,
)
from docstruct.config import ProcessingConfig, AgentConfig
from docstruct.exceptions import DocStructError

__all__ = [
    # Agents
    "BaseAgent",
    "AgentResult",
    "AgentChain",
    "BoundaryAgent",
    "ClassifierAgent",
    "SummaryAgent",
    "MetadataAgent",
    # Models
    "HeadingEntry",
    "TOCBoundary",
    "DocumentMetadata",
    "ExtractionResult",
    "LogEntry",
    # Configuration
    "ProcessingConfig",
    "AgentConfig",
    # Exceptions
    "DocStructError",
]

__version__ = "0.1.0"
