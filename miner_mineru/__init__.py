"""miner_mineru — LLM-based TOC extraction and JSON processing pipeline."""

from miner_mineru.agents import (
    BaseAgent,
    AgentResult,
    AgentChain,
    BoundaryAgent,
    ClassifierAgent,
    SummaryAgent,
    MetadataAgent,
)
from miner_mineru.models import (
    # TOC extraction models
    HeadingEntry,
    TOCBoundary,
    DocumentMetadata,
    ExtractionResult,
    LogEntry,
    # JSON processing models
    Block,
    BlockType,
    BlockRole,
    Span,
    TableCell,
    TableRow,
    Table,
    ListItem,
    Page,
    Document,
)
from miner_mineru.config import ProcessingConfig, AgentConfig
from miner_mineru.exceptions import MinerUError
from miner_mineru.pipeline.json_loader import load_mineru_json, save_cleaned_json

__all__ = [
    # Agents
    "BaseAgent",
    "AgentResult",
    "AgentChain",
    "BoundaryAgent",
    "ClassifierAgent",
    "SummaryAgent",
    "MetadataAgent",
    # Models (TOC)
    "HeadingEntry",
    "TOCBoundary",
    "DocumentMetadata",
    "ExtractionResult",
    "LogEntry",
    # Models (JSON)
    "Block",
    "BlockType",
    "BlockRole",
    "Span",
    "TableCell",
    "TableRow",
    "Table",
    "ListItem",
    "Page",
    "Document",
    # Configuration
    "ProcessingConfig",
    "AgentConfig",
    # Exceptions
    "MinerUError",
    # JSON Processing
    "load_mineru_json",
    "save_cleaned_json",
]

__version__ = "0.1.0"
