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
        api_version: str = "2024-02-15-preview",
    ):
        """Initialize Azure OpenAI embedder.

        Args:
            api_key: Azure OpenAI API key.
            api_endpoint: Azure OpenAI endpoint URL (e.g., https://{resource}.openai.azure.com/).
            model: Deployment name in Azure (not the model ID).
            api_version: Azure OpenAI API version (default: 2024-02-15-preview).
        """
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_endpoint,
        )
        self.model = model

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension for text-embedding-3-small (1536) or text-embedding-3-large (3072).

        Defaults to 1536 for Azure text-embedding-3-small deployments.
        Override by setting EMBEDDING_DIMENSIONS environment variable if using text-embedding-3-large.
        """
        return 1536

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
