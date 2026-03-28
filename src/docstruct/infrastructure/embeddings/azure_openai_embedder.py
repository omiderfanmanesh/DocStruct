"""Azure OpenAI embedding adapter implementing EmbeddingPort."""

from __future__ import annotations

from openai import AzureOpenAI

from ...domain.exceptions import EmbeddingDimensionError


class AzureOpenAIEmbedder:
    """Azure OpenAI embedding implementation supporting document and query embeddings.

    Uses Azure OpenAI API with automatic batching at 2048 texts per request.
    Supports deployment-based model specification for Azure endpoints.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_endpoint: str,
        model: str,
        dimensions: int = 1536,
        api_version: str = "2024-02-15-preview",
    ):
        """Initialize Azure OpenAI embedder.

        Args:
            api_key: Azure OpenAI API key.
            api_endpoint: Azure OpenAI endpoint URL (e.g., https://{resource}.openai.azure.com/).
            model: Deployment name in Azure (not the model ID).
            dimensions: Expected embedding dimensionality for the deployment.
            api_version: Azure OpenAI API version (default: 2024-02-15-preview).
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_endpoint,
        )
        self.model = model
        self._dimensions = dimensions

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension configured for the Azure deployment."""
        return self._dimensions

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "azure-openai"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of documents.

        Uses Azure OpenAI API with batching at 2048 texts per request.

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
                model=self.model,
                input=batch,
            )

            # Extract embeddings from response
            for embedding_obj in response.data:
                embedding = embedding_obj.embedding
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
            model=self.model,
            input=[text],
        )
        embedding = response.data[0].embedding
        if len(embedding) != self.dimensionality:
            raise EmbeddingDimensionError(
                f"Expected dimension {self.dimensionality}, got {len(embedding)}"
            )
        return embedding
