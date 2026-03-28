"""Factory for building embedding adapters from configuration."""

from __future__ import annotations

from ...application.ports import EmbeddingPort
from ...config import EmbeddingConfig
from .openai_embedder import OpenAIEmbedder
from .cohere_embedder import CohereEmbedder
from .azure_openai_embedder import AzureOpenAIEmbedder


def build_embedder(config: EmbeddingConfig) -> EmbeddingPort:
    """Build an embedder instance from configuration.

    Args:
        config: EmbeddingConfig with provider and model specifications.

    Returns:
        EmbeddingPort implementation (OpenAIEmbedder, CohereEmbedder, or AzureOpenAIEmbedder).

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

    elif provider == "azure-openai":
        if not config.api_key:
            raise ValueError(
                "AZURE_OPENAI_API_KEY environment variable is required for Azure OpenAI embeddings. "
                "Please set it and ensure your API key is valid."
            )
        if not config.api_endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable is required for Azure OpenAI embeddings. "
                "Example: https://{resource}.openai.azure.com/"
            )
        return AzureOpenAIEmbedder(
            api_key=config.api_key,
            api_endpoint=config.api_endpoint,
            model=config.model,
            dimensions=config.dimensions or 1536,
            api_version=config.api_version or "2024-02-15-preview",
        )

    else:
        raise ValueError(
            f"Unsupported embedding provider: {provider}. "
            f"Supported providers: openai, cohere, azure-openai. "
            f"Set EMBEDDING_PROVIDER to one of these values."
        )
