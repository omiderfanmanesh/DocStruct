"""
Unified configuration management for docstruct.

Supports both TOC extraction and JSON processing pipelines.
Hierarchical loading: hardcoded defaults → YAML → env vars → CLI args
"""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class ProcessingConfig:
    """Configuration for document processing pipelines."""
    
    # General settings
    min_confidence: float = 0.75  # OCR confidence threshold
    batch_size: int = 5           # Batch processing size
    parallel: bool = True          # Enable parallel processing
    max_workers: int = 4           # Max worker threads
    enable_caching: bool = True    # Enable result caching
    cache_ttl: int = 3600         # Cache TTL in seconds (1 hour)
    
    # Markdown-specific settings
    remove_headers: bool = False   # Remove detected headers from output
    remove_footers: bool = False   # Remove detected footers from output
    
    # JSON-specific settings
    parse_json_files: bool = True  # Parse JSON during extraction
    extract_blocks: bool = True    # Extract individual blocks
    include_metadata: bool = True  # Include metadata in output
    
    @classmethod
    def from_env(cls):
        """Load config from environment variables (MINER_ prefix)."""
        return cls(
            min_confidence=float(os.getenv('MINER_MIN_CONFIDENCE', '0.75')),
            batch_size=int(os.getenv('MINER_BATCH_SIZE', '5')),
            parallel=os.getenv('MINER_PARALLEL', 'true').lower() == 'true',
            max_workers=int(os.getenv('MINER_MAX_WORKERS', '4')),
            remove_headers=os.getenv('MINER_REMOVE_HEADERS', 'false').lower() == 'true',
            remove_footers=os.getenv('MINER_REMOVE_FOOTERS', 'false').lower() == 'true',
        )


@dataclass
class AgentConfig:
    """Configuration for LLM agents."""
    
    # Model settings
    model: str = "claude-haiku-4-5-20251001"  # Default Claude Haiku
    max_tokens: int = 4096                     # Max output tokens
    temperature: float = 0.0                   # Deterministic (no randomness)
    timeout: int = 30                          # Request timeout in seconds
    
    # Retry settings
    retry_count: int = 3                       # Max retry attempts
    retry_delay: int = 1                       # Delay between retries (seconds)
    
    # Provider settings
    provider: str = "anthropic"                # LLM provider (anthropic, azure)
    api_key: Optional[str] = None              # API key (from env if not set)
    api_endpoint: Optional[str] = None         # Custom endpoint
    
    def __post_init__(self):
        """Load API key from environment if not provided."""
        if not self.api_key:
            self.api_key = os.getenv('ANTHROPIC_API_KEY')
            if not self.api_key:
                self.api_key = os.getenv('AZURE_OPENAI_API_KEY')
    
    @classmethod
    def from_env(cls):
        """Load config from environment variables (MINER_AGENT_ prefix)."""
        return cls(
            model=os.getenv('MINER_AGENT_MODEL', 'claude-haiku-4-5-20251001'),
            max_tokens=int(os.getenv('MINER_AGENT_MAX_TOKENS', '4096')),
            temperature=float(os.getenv('MINER_AGENT_TEMPERATURE', '0.0')),
            timeout=int(os.getenv('MINER_AGENT_TIMEOUT', '30')),
            retry_count=int(os.getenv('MINER_AGENT_RETRY_COUNT', '3')),
            retry_delay=int(os.getenv('MINER_AGENT_RETRY_DELAY', '1')),
            provider=os.getenv('MINER_AGENT_PROVIDER', 'anthropic'),
        )


__all__ = [
    "ProcessingConfig",
    "AgentConfig",
]
