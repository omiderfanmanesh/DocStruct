"""Unit tests for embedding adapters (OpenAI and Cohere)."""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestOpenAIEmbedder:
    """Test OpenAI embedding adapter."""

    def test_dimensionality(self):
        """Test that OpenAIEmbedder has correct dimensionality."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
        assert embedder.dimensionality == 1536

    def test_provider_name(self):
        """Test that OpenAIEmbedder has correct provider name."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
        assert embedder.provider_name == "openai"

    def test_embed_documents_empty(self):
        """Test that embed_documents returns empty list for empty input."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        with patch("docstruct.infrastructure.embeddings.openai_embedder.OpenAI"):
            embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
            result = embedder.embed_documents([])
            assert result == []

    def test_embed_documents_batching(self):
        """Test that embed_documents batches at 2048 texts per call."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in range(10)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.openai_embedder.OpenAI", return_value=mock_client):
            embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
            texts = ["text1", "text2", "text3"] + ["text"] * 2045  # 2048 total
            result = embedder.embed_documents(texts)

            # Should have made 1 call for batch of 2048 + 1 call for remaining 3
            assert mock_client.embeddings.create.call_count == 2

    def test_embed_query(self):
        """Test embed_query calls client with single query."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder

        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.openai_embedder.OpenAI", return_value=mock_client):
            embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
            result = embedder.embed_query("test query")

            assert len(result) == 1536
            mock_client.embeddings.create.assert_called()

    def test_embed_documents_dimension_mismatch(self):
        """Test that EmbeddingDimensionError is raised on dimension mismatch."""
        from docstruct.infrastructure.embeddings.openai_embedder import OpenAIEmbedder
        from docstruct.domain.exceptions import EmbeddingDimensionError

        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1024)]  # Wrong dimension
        mock_client.embeddings.create.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.openai_embedder.OpenAI", return_value=mock_client):
            embedder = OpenAIEmbedder(api_key="test_key", model="text-embedding-3-small")
            with pytest.raises(EmbeddingDimensionError):
                embedder.embed_documents(["text"])


class TestCohereEmbedder:
    """Test Cohere embedding adapter."""

    def test_dimensionality(self):
        """Test that CohereEmbedder has correct dimensionality."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
        assert embedder.dimensionality == 1024

    def test_provider_name(self):
        """Test that CohereEmbedder has correct provider name."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
        assert embedder.provider_name == "cohere"

    def test_embed_documents_empty(self):
        """Test that embed_documents returns empty list for empty input."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2"):
            embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
            result = embedder.embed_documents([])
            assert result == []

    def test_embed_documents_input_type(self):
        """Test that embed_documents uses search_document input_type."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        mock_client = Mock()
        mock_response = Mock()
        mock_response.embeddings.float = [[0.1] * 1024 for _ in range(5)]
        mock_client.embed.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2", return_value=mock_client):
            embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
            texts = ["text1", "text2", "text3", "text4", "text5"]
            result = embedder.embed_documents(texts)

            # Verify input_type='search_document' was passed
            mock_client.embed.assert_called()
            call_kwargs = mock_client.embed.call_args[1]
            assert call_kwargs.get("input_type") == "search_document"

    def test_embed_query_input_type(self):
        """Test that embed_query uses search_query input_type."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        mock_client = Mock()
        mock_response = Mock()
        mock_response.embeddings.float = [[0.1] * 1024]
        mock_client.embed.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2", return_value=mock_client):
            embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
            result = embedder.embed_query("test query")

            # Verify input_type='search_query' was passed
            call_kwargs = mock_client.embed.call_args[1]
            assert call_kwargs.get("input_type") == "search_query"
            assert len(result) == 1024

    def test_embed_documents_batching(self):
        """Test that embed_documents batches at 96 texts per call."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder

        mock_client = Mock()
        mock_response = Mock()
        mock_response.embeddings.float = [[0.1] * 1024 for _ in range(96)]
        mock_client.embed.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2", return_value=mock_client):
            embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
            texts = ["text"] * 100  # More than one batch (96 + 4)
            result = embedder.embed_documents(texts)

            # Should have made 2 calls: 96 + 4
            assert mock_client.embed.call_count == 2

    def test_embed_documents_dimension_mismatch(self):
        """Test that EmbeddingDimensionError is raised on dimension mismatch."""
        from docstruct.infrastructure.embeddings.cohere_embedder import CohereEmbedder
        from docstruct.domain.exceptions import EmbeddingDimensionError

        mock_client = Mock()
        mock_response = Mock()
        mock_response.embeddings.float = [[0.1] * 1536]  # Wrong dimension
        mock_client.embed.return_value = mock_response

        with patch("docstruct.infrastructure.embeddings.cohere_embedder.ClientV2", return_value=mock_client):
            embedder = CohereEmbedder(api_key="test_key", model="embed-english-v3.0")
            with pytest.raises(EmbeddingDimensionError):
                embedder.embed_documents(["text"])
