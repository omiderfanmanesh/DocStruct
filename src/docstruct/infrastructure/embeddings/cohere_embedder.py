"""Cohere embedding adapter implementing EmbeddingPort."""

from __future__ import annotations

from cohere import ClientV2

from ...domain.exceptions import EmbeddingDimensionError


class CohereEmbedder:
    """Cohere embedding implementation supporting search_document and search_query modes.

    Uses Cohere's V2 API with automatic batching at 96 texts per request.
    Supports different input_type for documents vs queries to optimize embeddings.
    """

    def __init__(self, *, api_key: str, model: str = "embed-english-v3.0"):
        """Initialize Cohere embedder.

        Args:
            api_key: Cohere API key.
            model: Model name (default: embed-english-v3.0 which has dimensionality 1024).
        """
        self.client = ClientV2(api_key=api_key)
        self.model = model

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension for embed-english-v3.0."""
        return 1024

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "cohere"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of documents.

        Uses input_type='search_document' to optimize embeddings for document storage.
        Batches requests at 96 texts per API call.

        Args:
            texts: List of document texts.

        Returns:
            List of embedding vectors (one per input text). Empty list if input is empty.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = 96

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embed(
                model=self.model,
                texts=batch,
                input_type="search_document",
                embedding_types=["float"],
            )

            # Extract embeddings from response
            for embedding in response.embeddings.float:
                if len(embedding) != self.dimensionality:
                    raise EmbeddingDimensionError(
                        f"Expected dimension {self.dimensionality}, got {len(embedding)}"
                    )
                all_embeddings.append(embedding)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a query.

        Uses input_type='search_query' to optimize embeddings for query matching.

        Args:
            text: Query text.

        Returns:
            Embedding vector.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality.
        """
        response = self.client.embed(
            model=self.model,
            texts=[text],
            input_type="search_query",
            embedding_types=["float"],
        )
        embedding = response.embeddings.float[0]
        if len(embedding) != self.dimensionality:
            raise EmbeddingDimensionError(
                f"Expected dimension {self.dimensionality}, got {len(embedding)}"
            )
        return embedding
