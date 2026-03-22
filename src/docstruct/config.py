"""Configuration management for DocStruct."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _getenv_nonempty(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _default_agent_model(provider: str) -> str:
    normalized = provider.lower().strip()
    if normalized == "azure":
        return os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    if normalized == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    return "claude-haiku-4-5-20251001"


@dataclass
class ProcessingConfig:
    min_confidence: float = 0.75
    batch_size: int = 5
    parallel: bool = True
    max_workers: int = 4
    enable_caching: bool = True
    cache_ttl: int = 3600
    remove_headers: bool = False
    remove_footers: bool = False
    parse_json_files: bool = True
    extract_blocks: bool = True
    include_metadata: bool = True

    @classmethod
    def from_env(cls) -> "ProcessingConfig":
        return cls(
            min_confidence=float(os.getenv("DOCSTRUCT_MIN_CONFIDENCE", "0.75")),
            batch_size=int(os.getenv("DOCSTRUCT_BATCH_SIZE", "5")),
            parallel=os.getenv("DOCSTRUCT_PARALLEL", "true").lower() == "true",
            max_workers=int(os.getenv("DOCSTRUCT_MAX_WORKERS", "4")),
            remove_headers=os.getenv("DOCSTRUCT_REMOVE_HEADERS", "false").lower() == "true",
            remove_footers=os.getenv("DOCSTRUCT_REMOVE_FOOTERS", "false").lower() == "true",
        )


@dataclass
class AgentConfig:
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 1
    provider: str = "anthropic"
    api_key: str | None = None
    api_endpoint: str | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = (
                _getenv_nonempty("ANTHROPIC_API_KEY")
                or _getenv_nonempty("AZURE_OPENAI_API_KEY")
                or _getenv_nonempty("OPENAI_API_KEY")
            )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        provider = _getenv_nonempty("DOCSTRUCT_AGENT_PROVIDER") or os.getenv("LLM_PROVIDER", "anthropic")
        return cls(
            model=_getenv_nonempty("DOCSTRUCT_AGENT_MODEL") or _default_agent_model(provider),
            max_tokens=int(os.getenv("DOCSTRUCT_AGENT_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("DOCSTRUCT_AGENT_TEMPERATURE", "0.0")),
            timeout=int(os.getenv("DOCSTRUCT_AGENT_TIMEOUT", "30")),
            retry_count=int(os.getenv("DOCSTRUCT_AGENT_RETRY_COUNT", "3")),
            retry_delay=int(os.getenv("DOCSTRUCT_AGENT_RETRY_DELAY", "1")),
            provider=provider,
        )
