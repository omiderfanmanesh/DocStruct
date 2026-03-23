"""Application ports used for dependency inversion."""

from __future__ import annotations

from typing import Any, Protocol


class LLMPort(Protocol):
    supports_structured_output: bool

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        ...

    def create_structured_message(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        schema: Any,
    ) -> Any:
        ...


class FileReaderPort(Protocol):
    def read_lines(self, path: str) -> list[str]:
        ...


class EmbeddingPort(Protocol):
    """Port for embedding generation with provider abstraction."""

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension (e.g., 1536 for OpenAI, 1024 for Cohere)."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider name (e.g., 'openai', 'cohere')."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of documents.

        Args:
            texts: List of document texts.

        Returns:
            List of embedding vectors (one per input text). Empty list if input is empty.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality property.
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a query.

        Args:
            text: Query text.

        Returns:
            Embedding vector.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality property.
        """
        ...


class EmbeddingPort(Protocol):
    """Port for embedding generation with provider abstraction.

    Implementations must support specific input_type semantics (search_document vs search_query)
    as required by embeddings services like Cohere.
    """

    @property
    def dimensionality(self) -> int:
        """Embedding vector dimension (e.g., 1536 for OpenAI, 1024 for Cohere)."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider name (e.g., 'openai', 'cohere')."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of documents.

        Args:
            texts: List of document texts.

        Returns:
            List of embedding vectors (one per input text). Empty list if input is empty.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality property.
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a query.

        Args:
            text: Query text.

        Returns:
            Embedding vector.

        Raises:
            EmbeddingDimensionError: If returned vector dimension doesn't match dimensionality property.
        """
        ...


class Neo4jRetrievalPort(Protocol):
    """Port for Neo4j-backed hybrid retrieval (graph + full-text + vector modes)."""

    def retrieve_candidates(
        self,
        question: str,
        query_embedding: list[float] | None = None,
        *,
        limit: int = 6,
    ) -> list[Any]:  # Returns list of RetrievalCandidate
        """Retrieve document/section candidates from Neo4j.

        Combines graph matching, full-text search, and optional vector similarity using RRF fusion.

        Args:
            question: Natural language question or query.
            query_embedding: Optional embedding vector for vector similarity search.
                           If None, vector mode is skipped.
            limit: Maximum number of candidates to return.

        Returns:
            List of RetrievalCandidate objects sorted by RRF score (highest first).
            Empty list if no candidates found.
        """
        ...

    def get_document_index(self, document_id: str) -> Any | None:  # Returns SearchDocumentIndex | None
        """Retrieve the full SearchDocumentIndex for a given document.

        Reconstructs the document structure from Neo4j nodes and relationships.

        Args:
            document_id: Document ID to retrieve.

        Returns:
            SearchDocumentIndex instance, or None if document not found or is inactive.
        """
        ...

    def list_active_document_ids(self) -> list[str]:
        """List all active document IDs in the graph.

        Returns:
            List of document IDs with active=true.
        """
        ...
