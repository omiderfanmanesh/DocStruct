"""Block models for MinerU JSON extraction."""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import Enum


class BlockType(Enum):
    """Types of blocks extracted from PDF."""
    TITLE = "title"
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    EQUATION = "interline_equation"
    UNKNOWN = "unknown"


class BlockRole(Enum):
    """Detected role of block in document."""
    BODY = "body"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


@dataclass
class Span:
    """Lowest-level text unit with OCR confidence."""
    content: str
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None


@dataclass
class TableCell:
    """Single table cell."""
    col_idx: int
    content: str
    confidence: Optional[float] = None


@dataclass
class TableRow:
    """Single table row."""
    row_idx: int
    is_header: bool
    cells: List[TableCell] = field(default_factory=list)


@dataclass
class Table:
    """Structured table."""
    rows: List[TableRow] = field(default_factory=list)


@dataclass
class ListItem:
    """Single list item."""
    item_index: int
    content: str
    confidence: Optional[float] = None
    depth: int = 0


@dataclass
class Block:
    """Cleaned, normalized block from MinerU extraction."""
    block_id: str
    page_idx: int
    type: BlockType
    detected_role: "BlockRole" = None
    reclassified_type: Optional[str] = None
    content: Optional[str] = None
    confidence: Optional[float] = None
    has_ocr_issues: bool = False
    normalized_reading_order: int = 0
    source_spans_count: int = 0
    list_items: List[Dict[str, Any]] = field(default_factory=list)
    list_subtype: Optional[str] = None
    table: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.detected_role is None:
            self.detected_role = BlockRole.BODY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to exportable dictionary (cleaned, minimal keys)."""
        data = {
            "type": self.type.value,
        }

        if self.content:
            data["content"] = self.content
        if self.list_items:
            data["list"] = self.list_items
        if self.table:
            data["table"] = self.table

        return data
