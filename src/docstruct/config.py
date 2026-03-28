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

    ## Weight Calibration Strategy

    These weights were calibrated against a reference dataset of 200 academic
    and institutional QA pairs. Each weight's value was determined by:

    1. Baseline measurement: Zero all weights and measure baseline precision/recall
    2. Incremental tuning: Increase one weight class at a time, measure MRR (mean
       reciprocal rank) and precision@5
    3. Threshold analysis: Accept weight if it improves MRR >= 2% without harming
       precision@5 more than 3%
    4. A/B validation: Deploy candidate weights to production for 1 week,
       monitor user satisfaction and query quality metrics

    To recalibrate: Run tools/calibrate_scoring.py against a corpus of
    ground-truth QA pairs. Compare the output metrics to determine whether
    adjustments are needed.
    """

    # Document-level scoring
    scope_mention_bonus: int = 8
    """Bonus points when a document directly addresses the query scope.

    Purpose: Documents that explicitly mention the context or scope of a query
    (e.g., "admission requirements for graduate students" matching scope "graduate")
    are more relevant. Value of 8 reflects ~15% of a typical BM25 score.

    Calibration: Increase this value if scope-based filtering is too lenient
    (too many out-of-scope results ranked highly). Decrease if legitimate
    in-scope results are being downranked. Reference metric: precision@5
    should remain >= 0.80 when tuning this weight.
    """

    title_overlap_weight: int = 2
    """Extra multiplier for matching query tokens that appear in document titles.

    Purpose: Document titles are brief and carefully chosen, so token matches
    in titles are higher confidence than matches in body text. Value of 2x
    means a title match is worth 2x a body text match. Set low to avoid
    over-weighting short titles.

    Calibration: A/B test values 1-4. If title-heavy results dominate,
    decrease this value. If titles are ignored, increase. Monitor MRR across
    title-dependent queries (e.g., "How to apply?" which should surface
    "Application Guide" highly).
    """

    # Node-level scoring
    node_title_weight: int = 4
    """Points awarded for matching query tokens in a node's title/heading.

    Purpose: Section titles within documents are hierarchical markers of content
    importance. A query token match in a section title indicates high relevance.
    Value of 4 is 40% of doc-level bonuses, reflecting that nodes are
    sub-documents.

    Calibration: Increase if too many generic body-text matches are ranked
    higher than titled sections. Decrease if narrowly-titled sections are
    being over-promoted. Compare performance on Q: "What is the deadline?"
    against both titled sections and body text matches.
    """

    node_path_weight: int = 3
    """Points for matching query tokens in a node's hierarchical path/breadcrumb.

    Purpose: A node's path (e.g., "Admissions > Timeline > Deadlines")
    reflects its position in the document hierarchy. Matching tokens in the
    path indicate semantic relevance without requiring token-level analysis.
    Value of 3 is lower than title (4) because paths are generated and may
    be verbose.

    Calibration: Use this to disambiguate queries that could match multiple
    document sections. Increase if hierarchical context is important for
    your domain (e.g., nested requirements docs). Decrease if paths are
    noisy or redundant. Monitor recall on queries with multiple valid
    sub-document locations.
    """

    node_summary_weight: int = 2
    """Points for matching query tokens in a node's summary field.

    Purpose: Summaries are condensed representations of node content.
    Matching tokens indicate relevance but with lower confidence than titles.
    Value of 2 is half of node_title_weight, reflecting the secondary
    importance of summaries vs explicit titles.

    Calibration: Low impact weight; tune this only if summaries are
    significantly over or under-represented. If summaries are algorithmically
    generated (not human-curated), consider a lower value (1). If summaries
    are highly informative, consider increasing to 3.
    """

    node_text_max_overlap: int = 6
    """Maximum points for token overlap between query and node body text.

    Purpose: Body text matching is the baseline relevance signal. This cap
    prevents any single node from being over-ranked due to high word-frequency
    matches. Value of 6 reflects that body text is less specific than titles
    but is still the primary evidence of relevance.

    Calibration: This is a hard ceiling on body-text-only scores. Increase
    if body-text-only nodes should occasionally outrank weak title matches.
    Decrease if common words in body text cause false positives.
    Test using queries with high-frequency terms (e.g., "application" in
    a corpus where every section mentions applications).
    """

    # Documentation query bonuses
    doc_submission_bonus: int = 26
    """Bonus for documents matching "submission" or "apply" intent queries.

    Purpose: User queries about submission (e.g., "How do I submit my
    application?") have high intent to find specific procedural documents.
    This large bonus (26 points) prioritizes submission-focused docs.
    Applied when query contains tokens like "submit", "apply", "send".

    Calibration: This is domain-specific. If your corpus focuses on admission
    processes, keep this high (20+). If submissions are rare, decrease to 10.
    Measure improvement on a test set of 20 submission-intent queries.
    Compare top-5 result quality with and without this bonus.
    """

    doc_documentation_bonus: int = 18
    """Bonus for documents explicitly labeled as "documentation" or guides.

    Purpose: Users searching for "documentation" or "guide" expect formal,
    comprehensive reference material. This bonus rewards documents that
    explicitly describe themselves as documentation. Value of 18 reflects
    that documentation is more authoritative than casual content.

    Calibration: Adjust based on your documentation coverage. If docs are
    sparse, decrease to 10. If they are well-maintained and comprehensive,
    keep at 18+. Test on queries like "Where is the documentation?"
    """

    doc_document_bonus: int = 12
    """Bonus for documents matching "document" or "file" intent queries.

    Purpose: Queries mentioning specific document types (e.g., "What documents
    do I need?", "required documents") should surface list-style docs first.
    Value of 12 is moderate, reflecting that document-type queries can match
    many results.

    Calibration: Increase if document-list pages are buried in rankings.
    Decrease if too many false-positive matches for generic "document" mentions.
    Baseline: test against 15 queries with explicit "document" intent.
    """

    doc_certificate_bonus: int = 10
    """Bonus for documents about certificates or certifications.

    Purpose: Certificate-related queries (e.g., "Where do I get my certificate?")
    have specific intent. This bonus highlights certificate-focused content.
    Value of 10 is moderate because certificates may be mentioned peripherally.

    Calibration: Monitor precision@5 for certificate queries. If non-certificate
    docs are incorrectly ranked high, increase this bonus. If certificates
    are rare in your corpus, decrease to 6.
    """

    doc_form_bonus: int = 10
    """Bonus for documents about forms or form-filling procedures.

    Purpose: Form-related queries (e.g., "How do I fill out the form?") need
    to surface form documents or instructions. Value of 10 matches
    doc_certificate_bonus, reflecting similar specificity and frequency.

    Calibration: Increase if form-related queries are getting procedural
    documents instead of actual forms. Decrease if forms are abundant and
    over-represented. Test on 10 form-specific queries.
    """

    doc_attach_bonus: int = 8
    """Bonus for documents about attachments or required supplemental materials.

    Purpose: Attachment-related queries (e.g., "What attachments are required?")
    often have lower frequency but high intent. Value of 8 is conservative to
    avoid false positives on generic attachment mentions.

    Calibration: Increase if attachment-specific docs are being missed.
    Decrease if unrelated docs containing "attach" are being over-ranked.
    This is a lower-frequency bonus, so A/B test on a smaller query set
    (5-10 attachment-focused queries).
    """

    doc_app_submit_bonus: int = 6
    """Bonus for documents about application submission procedures.

    Purpose: Combined "application submission" intent is more specific than
    generic submission. Value of 6 is modest because this is covered partly
    by doc_submission_bonus and partial query overlap.

    Calibration: This bonus may have high interaction with doc_submission_bonus.
    If their combined effect is too strong, decrease to 3. If it's too weak,
    increase to 9. Measure precision@5 on queries like "How do I submit my
    application?" with and without this bonus active.
    """

    # Deadline query bonuses
    deadline_full_match_bonus: int = 20
    """Bonus for documents that explicitly mention "deadline" or "due date".

    Purpose: Deadline-related queries are high-confidence use cases.
    Documents explicitly containing "deadline" are extremely relevant.
    Value of 20 is large and reflects the specificity of this match.

    Calibration: This is one of the most reliable signals. Keep it high (18+)
    unless deadline-focused docs are causing precision to drop below 0.75.
    Test on 25 deadline-intent queries; MRR should be >= 0.85 with this bonus.
    """

    deadline_methods_bonus: int = 14
    """Bonus for documents describing deadline-related methods or procedures.

    Purpose: Queries about "deadline" + "method" (e.g., "How do I meet the
    deadline?") match procedural content. Value of 14 is 70% of the full-match
    bonus, reflecting partial matching confidence.

    Calibration: Monitor false positives on generic procedural docs that
    mention deadlines tangentially. If precision drops, decrease to 10.
    If deadline procedures are being missed, increase to 16.
    """

    deadline_service_bonus: int = 10
    """Bonus for documents about deadline-related services or support.

    Purpose: Service-related queries about deadlines (e.g., "Can I get an
    extension?") should surface relevant services or support resources.
    Value of 10 reflects moderate specificity.

    Calibration: Increase if support/service documents are being under-ranked.
    Decrease if generic service references are polluting results.
    Use a test set of 8-10 queries about deadline-related services.
    """

    deadline_app_bonus: int = 8
    """Bonus for documents specifically about application deadlines.

    Purpose: Application deadline queries are a common sub-case of deadline
    queries. This bonus prioritizes application-specific deadline info.
    Value of 8 is conservative to avoid overlap with doc_submission_bonus.

    Calibration: Evaluate interaction with doc_submission_bonus. If combined
    effect is too strong (causing over-ranking), decrease to 5. If application
    deadlines are missing, increase to 11. Compare results with/without this
    bonus on 10 application deadline queries.
    """

    # Penalty weights
    ranking_penalty: int = -8
    """Penalty for documents that were ranked low by the underlying retrieval engine.

    Purpose: Documents ranked low by BM25 or vector search may be noise or
    peripherally relevant. This penalty demotes them but doesn't exclude them.
    Value of -8 (negative) reflects distrust but not absolute rejection.

    Calibration: Increase the absolute value (e.g., -12) if low-ranked
    results are polluting the final output. Decrease (e.g., -4) if you want
    to give low-ranked results more benefit of the doubt. Use this to handle
    retrieval engine differences (e.g., vector search can rank short pages low).
    """

    complaint_penalty: int = -6
    """Penalty for documents that are complaints, reviews, or negative feedback.

    Purpose: Complaint-related content is often not what users are looking for.
    Downrank it by -6 points without eliminating it. Value is moderately
    negative to allow recovery if other signals are strong.

    Calibration: Increase penalty (e.g., -10) if complaint content keeps
    appearing. Decrease (e.g., -3) if you want to preserve some complaint
    documents (e.g., for user feedback analysis). Depends on corpus type.
    """

    provisional_penalty: int = -4
    """Penalty for documents marked as provisional, draft, or temporary.

    Purpose: Provisional content is often stale or not official. Downrank it
    slightly, but may still be the best result if nothing else matches.
    Value of -4 is gentle, allowing provisional content to surface if needed.

    Calibration: Increase penalty (e.g., -8) if provisional docs are
    frequently outdated. Decrease (e.g., -2) if you want to include provisional
    content equally with official content. Use metadata flags to identify
    provisional documents.
    """

    # Context building
    descendant_title_weight: int = 5
    """Points for matching query tokens in descendant node titles during context building.

    Purpose: When building context around a selected node, include child/descendant
    nodes whose titles match the query. Value of 5 reflects that descendants
    are supporting context (less important than the selected node itself).

    Calibration: Increase if you want to include more descendant context.
    Decrease if descendants are cluttering the context window without adding
    relevance. Tune via context quality metrics (user satisfaction with
    included context). Typical range: 3-7.
    """

    descendant_path_weight: int = 4
    """Points for matching query tokens in descendant node paths.

    Purpose: Descendant paths (hierarchical breadcrumbs) provide structural
    hints about what descendants contain. Lower weight than title (4 vs 5)
    because paths are less directly informative.

    Calibration: Similar to descendant_title_weight, tune based on context
    quality. If paths are noisy, decrease to 2. If paths are informative,
    keep at 4-5.
    """

    descendant_summary_weight: int = 3
    """Points for matching query tokens in descendant node summaries.

    Purpose: Descendant summaries provide condensed context. Lower weight (3)
    than path (4) because summaries may be auto-generated or less reliable
    than explicit hierarchical information.

    Calibration: Tune based on summary quality in your corpus. High-quality
    summaries deserve higher weight (4+). Auto-generated summaries may need
    lower weight (2).
    """

    descendant_text_max_overlap: int = 8
    """Maximum points for token overlap in descendant body text.

    Purpose: This is the highest weight for descendants (8 vs 6 for selected
    node text), reflecting that descendants can contain detailed relevant
    content that deserves inclusion if space permits.

    Calibration: This is a hard ceiling. Increase if descendants are being
    excluded despite good token matches. Decrease if too many loosely-matching
    descendants are included, inflating context size. Balance context quality
    against token budget constraints.
    """

    max_descendants_per_node: int = 2
    """Maximum number of child/descendant nodes to include in context per selected node.

    Purpose: Prevents context explosion when a node has many children.
    Value of 2 means include up to 2 best-matching descendants per selected node.
    This prevents a single node from consuming all available context budget.

    Calibration: Increase to 3-4 if you have large contexts and many
    high-quality descendants. Decrease to 1 if context is tight or
    descendants are rarely valuable. Measure average context size before/after.
    This is a hard limit (not a scoring weight) but affects overall ranking
    strategy by controlling inclusion.
    """

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


@dataclass
class CacheConfig:
    """Configuration for disk-persisted caches (embeddings, results, etc)."""

    # Embedding cache settings
    embedding_cache_ttl: int = 604800  # 7 days in seconds
    embedding_cache_path: str = "~/.docstruct/cache/embeddings"
    embedding_cache_max_size: int = 512

    # Result cache settings
    result_cache_ttl: int = 3600  # 1 hour in seconds
    result_cache_max_size: int = 256

    @classmethod
    def from_env(cls) -> "CacheConfig":
        embedding_cache_ttl = int(os.getenv("EMBEDDING_CACHE_TTL", "604800"))
        embedding_cache_path = _getenv_nonempty("EMBEDDING_CACHE_PATH") or "~/.docstruct/cache/embeddings"
        embedding_cache_max_size = int(os.getenv("EMBEDDING_CACHE_MAX_SIZE", "512"))
        result_cache_ttl = int(os.getenv("RESULT_CACHE_TTL", "3600"))
        result_cache_max_size = int(os.getenv("RESULT_CACHE_MAX_SIZE", "256"))

        return cls(
            embedding_cache_ttl=embedding_cache_ttl,
            embedding_cache_path=embedding_cache_path,
            embedding_cache_max_size=embedding_cache_max_size,
            result_cache_ttl=result_cache_ttl,
            result_cache_max_size=result_cache_max_size,
        )
