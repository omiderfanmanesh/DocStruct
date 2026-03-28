"""Caching layer for embeddings, search results, and document trees."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A cached value with timestamp and TTL tracking."""

    value: T
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) >= self.ttl


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "hit_rate": round(self.hit_rate, 3),
        }


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL expiration.

    Args:
        max_size: Maximum number of entries.
        default_ttl: Default time-to-live in seconds.
        name: Cache name (for logging/metrics).
    """

    def __init__(self, max_size: int = 256, default_ttl: float = 3600.0, name: str = "cache"):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self.name = name
        self._data: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = CacheStats()

    def get(self, key: str) -> T | None:
        """Get a value by key. Returns None if not found or expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            if entry.is_expired:
                del self._data[key]
                self._stats.misses += 1
                self._stats.size = len(self._data)
                return None
            # Move to end (most recently used)
            self._data.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1
            return entry.value

    def put(self, key: str, value: T, ttl: float | None = None) -> None:
        """Store a value with optional TTL override."""
        with self._lock:
            if key in self._data:
                del self._data[key]
            elif len(self._data) >= self._max_size:
                self._data.popitem(last=False)  # Remove least recently used
                self._stats.evictions += 1
            self._data[key] = CacheEntry(
                value=value,
                created_at=time.monotonic(),
                ttl=ttl if ttl is not None else self._default_ttl,
            )
            self._stats.size = len(self._data)

    def invalidate(self, key: str) -> bool:
        """Remove a specific key. Returns True if key existed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._stats.size = len(self._data)
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._data.clear()
            self._stats.size = 0

    @property
    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                size=len(self._data),
            )


def _hash_key(*parts: str) -> str:
    """Create a deterministic cache key from multiple string parts."""
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


# ---- Specialized caches ----

# Embedding cache: caches query embeddings to avoid redundant API calls
_embedding_cache: LRUCache[list[float]] = LRUCache(
    max_size=512,
    default_ttl=7200.0,  # 2 hours
    name="embedding",
)

# Result cache: caches full search answers for identical queries
_result_cache: LRUCache[Any] = LRUCache(
    max_size=128,
    default_ttl=1800.0,  # 30 minutes
    name="result",
)

# Document tree cache: caches reconstructed document indexes from Neo4j
_document_cache: LRUCache[Any] = LRUCache(
    max_size=64,
    default_ttl=3600.0,  # 1 hour
    name="document_tree",
)


def get_cached_embedding(text: str, provider: str, model: str) -> list[float] | None:
    """Get a cached embedding vector for the given text/provider/model."""
    key = _hash_key(text, provider, model)
    return _embedding_cache.get(key)


def cache_embedding(text: str, provider: str, model: str, embedding: list[float]) -> None:
    """Cache an embedding vector."""
    key = _hash_key(text, provider, model)
    _embedding_cache.put(key, embedding)


def get_cached_result(question: str, retrieval_backend: str) -> Any | None:
    """Get a cached search result for the given question/backend."""
    key = _hash_key(question, retrieval_backend)
    return _result_cache.get(key)


def cache_result(question: str, retrieval_backend: str, result: Any) -> None:
    """Cache a search result."""
    key = _hash_key(question, retrieval_backend)
    _result_cache.put(key, result)


def get_cached_document(document_id: str) -> Any | None:
    """Get a cached document index."""
    key = _hash_key(document_id)
    return _document_cache.get(key)


def cache_document(document_id: str, document: Any) -> None:
    """Cache a document index."""
    key = _hash_key(document_id)
    _document_cache.put(key, document)


def get_all_cache_stats() -> dict[str, dict[str, Any]]:
    """Get stats for all caches."""
    return {
        "embedding": _embedding_cache.stats.to_dict(),
        "result": _result_cache.stats.to_dict(),
        "document_tree": _document_cache.stats.to_dict(),
    }


def clear_all_caches() -> None:
    """Clear all caches (useful for testing)."""
    _embedding_cache.clear()
    _result_cache.clear()
    _document_cache.clear()
