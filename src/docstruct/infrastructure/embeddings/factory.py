"""Factory for building embedding adapters from configuration."""

from __future__ import annotations

from ...application.ports import EmbeddingPort
from ...config import EmbeddingConfig
from .openai_embedder import OpenAIEmbedder
from .cohere_embedder import CohereEmbedder


def build_embedder(config: EmbeddingConfig) -> EmbeddingPort:
    """Build an embedder instance from configuration.

    Args:
        config: EmbeddingConfig with provider and model specifications.

    Returns:
        EmbeddingPort implementation (OpenAIEmbedder or CohereEmbedder).

    Raises:
        ValueError: If provider is unsupported or configuration is invalid.
    """
    provider = config.provider.lower()

    if provider == "openai":
        if not config.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAI embeddings. "
                "Please set it and ensure your API key is valid."
            )
        return OpenAIEmbedder(
            api_key=config.api_key,
            model=config.model,
        )

    elif provider == "cohere":
        if not config.api_key:
            raise ValueError(
                "COHERE_API_KEY environment variable is required for Cohere embeddings. "
                "Please set it and ensure your API key is valid."
            )
        return CohereEmbedder(
            api_key=config.api_key,
            model=config.model,
        )

    else:
        raise ValueError(
            f"Unsupported embedding provider: {provider}. "
            f"Supported providers: openai, cohere. "
            f"Set EMBEDDING_PROVIDER to one of these values."
        )
