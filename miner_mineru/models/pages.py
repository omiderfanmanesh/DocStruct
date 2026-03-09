"""Document models for MinerU extraction results."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .blocks import Block


@dataclass
class Page:
    """Single page with extracted blocks."""
    page_idx: int
    blocks: List[Block] = field(default_factory=list)
    page_width: Optional[float] = None
    page_height: Optional[float] = None


@dataclass
class Document:
    """Complete extracted document."""
    source_file: str
    pages: List[Page] = field(default_factory=list)
    total_pages: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_blocks(self) -> List[Block]:
        """Get all blocks from all pages."""
        blocks = []
        for page in self.pages:
            blocks.extend(page.blocks)
        return blocks

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (cleaned output)."""
        return {
            "metadata": {
                "source_file": self.source_file,
                "total_pages": self.total_pages,
                "total_blocks": len(self.get_all_blocks()),
            },
            "blocks": [block.to_dict() for block in self.get_all_blocks()]
        }
