"""Unit tests for Azure OpenAI embedding adapter."""

import pytest
from unittest.mock import Mock, patch


class TestAzureOpenAIEmbedderFactory:
    """Test factory support for Azure OpenAI embedder."""

    def test_factory_builds_azure_openai_embedder(self):
        """Test that factory correctly builds AzureOpenAIEmbedder."""
        from docstruct.infrastructure.embeddings.factory import build_embedder
        from docstruct.config import EmbeddingConfig

        config = EmbeddingConfig(
            provider="azure-openai",
            model="text-embedding-3-small",
            dimensions=1536,
            api_key="test_key",
            api_endpoint="https://test.openai.azure.com/",
            api_version="2024-02-15-preview",
        )

        with patch("docstruct.infrastructure.embeddings.azure_openai_embedder.AzureOpenAI"):
            embedder = build_embedder(config)

            # Verify correct embedder type was created
            from docstruct.infrastructure.embeddings.azure_openai_embedder import AzureOpenAIEmbedder
            assert isinstance(embedder, AzureOpenAIEmbedder)
            assert embedder.provider_name == "azure-openai"
            assert embedder.dimensionality == 1536

    def test_factory_requires_azure_api_key(self):
        """Test that factory raises error when Azure API key is missing."""
        from docstruct.infrastructure.embeddings.factory import build_embedder
        from docstruct.config import EmbeddingConfig

        config = EmbeddingConfig(
            provider="azure-openai",
            model="text-embedding-3-small",
            dimensions=1536,
            api_key=None,  # Missing key
            api_endpoint="https://test.openai.azure.com/",
        )

        with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
            build_embedder(config)

    def test_factory_requires_azure_endpoint(self):
        """Test that factory raises error when Azure endpoint is missing."""
        from docstruct.infrastructure.embeddings.factory import build_embedder
        from docstruct.config import EmbeddingConfig

        config = EmbeddingConfig(
            provider="azure-openai",
            model="text-embedding-3-small",
            dimensions=1536,
            api_key="test_key",
            api_endpoint=None,  # Missing endpoint
        )

        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            build_embedder(config)

    def test_factory_uses_default_api_version(self):
        """Test that factory uses default API version when not specified."""
        from docstruct.infrastructure.embeddings.factory import build_embedder
        from docstruct.config import EmbeddingConfig

        config = EmbeddingConfig(
            provider="azure-openai",
            model="text-embedding-3-small",
            dimensions=1536,
            api_key="test_key",
            api_endpoint="https://test.openai.azure.com/",
            api_version=None,  # Not specified
        )

        with patch("docstruct.infrastructure.embeddings.azure_openai_embedder.AzureOpenAI") as mock_azure:
            embedder = build_embedder(config)

            # Verify AzureOpenAI was initialized with default version
            mock_azure.assert_called_once()
            call_kwargs = mock_azure.call_args[1]
            assert call_kwargs["api_version"] == "2024-02-15-preview"
            assert embedder.dimensionality == 1536

    def test_factory_passes_large_embedding_dimensions(self):
        """Test that factory preserves configured dimensions for larger Azure deployments."""
        from docstruct.infrastructure.embeddings.factory import build_embedder
        from docstruct.config import EmbeddingConfig

        config = EmbeddingConfig(
            provider="azure-openai",
            model="text-embedding-3-large",
            dimensions=3072,
            api_key="test_key",
            api_endpoint="https://test.openai.azure.com/",
            api_version="2024-02-15-preview",
        )

        with patch("docstruct.infrastructure.embeddings.azure_openai_embedder.AzureOpenAI"):
            embedder = build_embedder(config)
            assert embedder.dimensionality == 3072


class TestAzureOpenAIConfig:
    """Test EmbeddingConfig support for Azure OpenAI."""

    def test_config_from_env_azure_openai(self):
        """Test EmbeddingConfig.from_env() parses Azure OpenAI environment variables."""
        import os
        from docstruct.config import EmbeddingConfig

        env_vars = {
            "EMBEDDING_PROVIDER": "azure-openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "AZURE_OPENAI_API_KEY": "test_key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
            "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        }

        with patch.dict(os.environ, env_vars):
            config = EmbeddingConfig.from_env()

            assert config.provider == "azure-openai"
            assert config.model == "text-embedding-3-small"
            assert config.dimensions == 1536
            assert config.api_key == "test_key"
            assert config.api_endpoint == "https://test.openai.azure.com/"
            assert config.api_version == "2024-02-15-preview"

    def test_config_detects_azure_openai_dimensions(self):
        """Test that EmbeddingConfig auto-detects dimensions for Azure OpenAI models."""
        import os
        from docstruct.config import EmbeddingConfig

        # Test text-embedding-3-small
        env_vars = {
            "EMBEDDING_PROVIDER": "azure-openai",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "AZURE_OPENAI_API_KEY": "test_key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        }

        with patch.dict(os.environ, env_vars):
            config = EmbeddingConfig.from_env()
            assert config.dimensions == 1536

        # Test text-embedding-3-large
        env_vars["EMBEDDING_MODEL"] = "text-embedding-3-large"
        with patch.dict(os.environ, env_vars):
            config = EmbeddingConfig.from_env()
            assert config.dimensions == 3072
