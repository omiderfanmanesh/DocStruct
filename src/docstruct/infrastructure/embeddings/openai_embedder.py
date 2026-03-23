"""OpenAI embedding adapter implementing EmbeddingPort."""

from __future__ import annotations

from openai import OpenAI

from ...domain.exceptions import EmbeddingDimensionError


class OpenAIEmbedder:
    """OpenAI embedding implementation using text-embedding-3-small by default.

    Uses OpenAI's embedding API with automatic batching at 2048 texts per request.
    """

    def __init__(self, *, api_key: str, model: str = "text-embedding-3-small"):
        """Initialize OpenAI embedder.

        Args:
            api_key: OpenAI API key.
            model: Model name (default: text-embedding-3-small which has dimensionality 1536).
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension for text-embedding-3-small."""
        return 1536

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "openai"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of documents.

        Batches requests at 2048 texts per API call.

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
        batch_size = 2048

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model,
            )

            # Extract embeddings from response
            for data in response.data:
                embedding = data.embedding
                if len(embedding) != self.dimensionality:
                    raise EmbeddingDimensionError(
                        f"Expected dimension {self.dimensionality}, got {len(embedding)}"
                    )
                all_embeddings.append(embedding)

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a query.

        Args:
            text: Query text.

        Returns:
            Embedding vector.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality.
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.model,
        )
        embedding = response.data[0].embedding
        if len(embedding) != self.dimensionality:
            raise EmbeddingDimensionError(
                f"Expected dimension {self.dimensionality}, got {len(embedding)}"
            )
        return embedding
