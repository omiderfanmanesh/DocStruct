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


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection and behavior."""

    uri: str
    auth: str | tuple[str, str]  # "none" or "user/password"
    max_pool_size: int = 50
    readiness_retries: int = 30
    readiness_backoff_base: float = 1.0

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        uri = _getenv_nonempty("NEO4J_URI")
        if not uri:
            raise ValueError("NEO4J_URI environment variable is required")

        auth = _getenv_nonempty("NEO4J_AUTH")
        if not auth:
            raise ValueError("NEO4J_AUTH environment variable is required (set to 'none' or 'user/password')")

        # Parse auth: if "none", keep as string; if "user/password", split into tuple
        if auth.lower() == "none":
            auth_value: str | tuple[str, str] = auth
        elif "/" in auth:
            parts = auth.split("/", 1)
            auth_value = (parts[0], parts[1])
        else:
            raise ValueError("NEO4J_AUTH must be 'none' or 'user/password' format")

        return cls(
            uri=uri,
            auth=auth_value,
            max_pool_size=int(os.getenv("NEO4J_MAX_POOL_SIZE", "50")),
            readiness_retries=int(os.getenv("NEO4J_READINESS_RETRIES", "30")),
            readiness_backoff_base=float(os.getenv("NEO4J_READINESS_BACKOFF_BASE", "1.0")),
        )


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation and providers."""

    provider: str  # "openai" or "cohere"
    model: str
    dimensions: int | None = None

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        provider = _getenv_nonempty("EMBEDDING_PROVIDER") or "openai"
        model = _getenv_nonempty("EMBEDDING_MODEL") or "text-embedding-3-small"

        # Auto-detect dimensions based on provider and model
        dimensions: int | None = None
        dimensions_env = _getenv_nonempty("EMBEDDING_DIMENSIONS")
        if dimensions_env:
            dimensions = int(dimensions_env)
        else:
            # Default dimensions for common models
            if provider.lower() == "openai":
                if "3-small" in model:
                    dimensions = 1536
                elif "3-large" in model:
                    dimensions = 3072
            elif provider.lower() == "cohere":
                if "v3" in model:
                    dimensions = 1024

        if not dimensions:
            raise ValueError(
                f"Could not determine embedding dimensions for provider={provider}, model={model}. "
                "Set EMBEDDING_DIMENSIONS explicitly."
            )

        return cls(provider=provider, model=model, dimensions=dimensions)


@dataclass
class RetrievalConfig:
    """Configuration for Neo4j-backed retrieval modes."""

    max_candidates: int = 6
    enable_graph: bool = True
    enable_fulltext: bool = True
    enable_vector: bool = True

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        enable_graph = os.getenv("RETRIEVAL_ENABLE_GRAPH", "true").lower() == "true"
        enable_fulltext = os.getenv("RETRIEVAL_ENABLE_FULLTEXT", "true").lower() == "true"
        enable_vector = os.getenv("RETRIEVAL_ENABLE_VECTOR", "true").lower() == "true"

        if not (enable_graph or enable_fulltext or enable_vector):
            raise ValueError("At least one retrieval mode (graph, fulltext, or vector) must be enabled")

        return cls(
            max_candidates=int(os.getenv("RETRIEVAL_MAX_CANDIDATES", "6")),
            enable_graph=enable_graph,
            enable_fulltext=enable_fulltext,
            enable_vector=enable_vector,
        )
