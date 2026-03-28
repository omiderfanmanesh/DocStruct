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

    provider: str  # "openai", "cohere", or "azure-openai"
    model: str
    dimensions: int | None = None
    api_key: str | None = None
    api_endpoint: str | None = None  # Azure-specific
    api_version: str | None = None  # Azure-specific

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        provider = _getenv_nonempty("EMBEDDING_PROVIDER") or "openai"
        model = _getenv_nonempty("EMBEDDING_MODEL") or "text-embedding-3-small"

        # Get API credentials based on provider
        api_key: str | None = None
        api_endpoint: str | None = None
        api_version: str | None = None

        provider_lower = provider.lower()

        if provider_lower == "openai":
            api_key = _getenv_nonempty("OPENAI_API_KEY")
        elif provider_lower == "cohere":
            api_key = _getenv_nonempty("COHERE_API_KEY")
        elif provider_lower == "azure-openai":
            api_key = _getenv_nonempty("AZURE_OPENAI_API_KEY")
            api_endpoint = _getenv_nonempty("AZURE_OPENAI_ENDPOINT")
            api_version = _getenv_nonempty("AZURE_OPENAI_API_VERSION") or "2024-02-15-preview"

        # Auto-detect dimensions based on provider and model
        dimensions: int | None = None
        dimensions_env = _getenv_nonempty("EMBEDDING_DIMENSIONS")
        if dimensions_env:
            dimensions = int(dimensions_env)
        else:
            # Default dimensions for common models
            if provider_lower == "openai" or provider_lower == "azure-openai":
                if "3-small" in model or "text-embedding-3-small" in model:
                    dimensions = 1536
                elif "3-large" in model or "text-embedding-3-large" in model:
                    dimensions = 3072
            elif provider_lower == "cohere":
                if "v3" in model:
                    dimensions = 1024

        if not dimensions:
            raise ValueError(
                f"Could not determine embedding dimensions for provider={provider}, model={model}. "
                "Set EMBEDDING_DIMENSIONS explicitly."
            )

        return cls(
            provider=provider,
            model=model,
            dimensions=dimensions,
            api_key=api_key,
            api_endpoint=api_endpoint,
            api_version=api_version,
        )


@dataclass
class RetrievalConfig:
    """Configuration for Neo4j-backed retrieval modes."""

    max_candidates: int = 6
    enable_graph: bool = True
    enable_fulltext: bool = True
    enable_vector: bool = True
    rewrite_similarity_threshold: float = 0.6

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
            rewrite_similarity_threshold=float(os.getenv("REWRITE_SIMILARITY_THRESHOLD", "0.6")),
        )


@dataclass
class ScoringConfig:
    """Configurable weights for heuristic scoring.

    All weights can be tuned via environment variables for A/B testing
    and per-deployment calibration.
    """

    # Document-level scoring
    scope_mention_bonus: int = 8
    title_overlap_weight: int = 2  # extra weight for title token overlap

    # Node-level scoring
    node_title_weight: int = 4
    node_path_weight: int = 3
    node_summary_weight: int = 2
    node_text_max_overlap: int = 6

    # Documentation query bonuses
    doc_submission_bonus: int = 26
    doc_documentation_bonus: int = 18
    doc_document_bonus: int = 12
    doc_certificate_bonus: int = 10
    doc_form_bonus: int = 10
    doc_attach_bonus: int = 8
    doc_app_submit_bonus: int = 6

    # Deadline query bonuses
    deadline_full_match_bonus: int = 20
    deadline_methods_bonus: int = 14
    deadline_service_bonus: int = 10
    deadline_app_bonus: int = 8

    # Penalty weights
    ranking_penalty: int = -8
    complaint_penalty: int = -6
    provisional_penalty: int = -4

    # Context building
    descendant_title_weight: int = 5
    descendant_path_weight: int = 4
    descendant_summary_weight: int = 3
    descendant_text_max_overlap: int = 8
    max_descendants_per_node: int = 2

    @classmethod
    def from_env(cls) -> "ScoringConfig":
        return cls(
            scope_mention_bonus=int(os.getenv("SCORING_SCOPE_MENTION_BONUS", "8")),
            node_title_weight=int(os.getenv("SCORING_NODE_TITLE_WEIGHT", "4")),
            node_path_weight=int(os.getenv("SCORING_NODE_PATH_WEIGHT", "3")),
            node_summary_weight=int(os.getenv("SCORING_NODE_SUMMARY_WEIGHT", "2")),
            doc_submission_bonus=int(os.getenv("SCORING_DOC_SUBMISSION_BONUS", "26")),
            doc_documentation_bonus=int(os.getenv("SCORING_DOC_DOCUMENTATION_BONUS", "18")),
        )


@dataclass
class ContextConfig:
    """Configuration for dynamic context window management."""

    # Per-block character limit
    max_chars_per_block: int = 1600
    # Total context budget for the LLM prompt
    total_context_budget: int = 12000
    # Maximum context blocks to send to the LLM
    max_context_blocks: int = 8
    # Whether to dynamically adjust block size based on selected node count
    dynamic_sizing: bool = True
    # Token budget overflow policy: 'truncate' (drop lowest-priority) or 'reject' (raise error)
    overflow_policy: str = "truncate"
    # Batch size for processing contexts in chunks (prevents OOM on large document sets)
    max_batch_size: int = 50

    @classmethod
    def from_env(cls) -> "ContextConfig":
        return cls(
            max_chars_per_block=int(os.getenv("CONTEXT_MAX_CHARS_PER_BLOCK", "1600")),
            total_context_budget=int(os.getenv("CONTEXT_TOTAL_BUDGET", "12000")),
            max_context_blocks=int(os.getenv("CONTEXT_MAX_BLOCKS", "8")),
            dynamic_sizing=os.getenv("CONTEXT_DYNAMIC_SIZING", "true").lower() == "true",
            overflow_policy=os.getenv("CONTEXT_OVERFLOW_POLICY", "truncate"),
            max_batch_size=int(os.getenv("CONTEXT_MAX_BATCH_SIZE", "50")),
        )

    def effective_max_chars(self, selected_node_count: int) -> int:
        """Calculate the per-block max chars based on total budget and node count.

        When dynamic_sizing is enabled, the per-block limit is adjusted so that
        the total context fits within the budget.
        """
        if not self.dynamic_sizing or selected_node_count <= 0:
            return self.max_chars_per_block
        # Each node may produce ~2 context blocks (node + best descendant)
        estimated_blocks = min(selected_node_count * 2, self.max_context_blocks)
        if estimated_blocks <= 0:
            return self.max_chars_per_block
        dynamic_limit = self.total_context_budget // estimated_blocks
        return min(dynamic_limit, self.max_chars_per_block)
