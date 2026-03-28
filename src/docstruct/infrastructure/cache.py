"""Caching layer for embeddings, search results, and document trees."""

from __future__ import annotations

import hashlib
import logging
import os
import shelve
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

logger = logging.getLogger("docstruct.cache")

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


class DiskLRUCache(LRUCache[T]):
    """Disk-persisted LRU cache with TTL expiration using shelve.

    Extends LRUCache to add disk persistence via shelve. Entries are automatically
    loaded from disk at initialization and synced on every put(). TTL expiry is
    checked on get() and during load, with expired entries silently removed.

    Args:
        max_size: Maximum number of entries in memory.
        default_ttl: Default time-to-live in seconds.
        path: Directory path for shelf file (default: ~/.docstruct/cache/embeddings).
        name: Cache name (for logging/metrics).
    """

    def __init__(
        self,
        max_size: int = 512,
        default_ttl: float = 604800.0,  # 7 days
        path: str | None = None,
        name: str = "disk_cache",
    ):
        super().__init__(max_size=max_size, default_ttl=default_ttl, name=name)
        self._shelf_path = path or os.path.expanduser("~/.docstruct/cache/embeddings")
        self._lock = threading.RLock()  # Use RLock for nested locking compatibility

        # Create directory if it doesn't exist
        Path(self._shelf_path).parent.mkdir(parents=True, exist_ok=True)

        # Load existing data from disk
        self.load_from_disk()

    def load_from_disk(self) -> None:
        """Load cache entries from disk, removing expired entries."""
        with self._lock:
            try:
                with shelve.open(self._shelf_path) as shelf:
                    current_time = time.monotonic()
                    keys_to_delete = []

                    # Load all entries and check for expiry
                    for key in list(shelf.keys()):
                        try:
                            entry = shelf[key]
                            # Check if entry is expired
                            if isinstance(entry, CacheEntry):
                                if (current_time - entry.created_at) >= entry.ttl:
                                    keys_to_delete.append(key)
                                else:
                                    self._data[key] = entry
                        except Exception as e:
                            logger.debug(f"Error loading cache entry {key}: {e}")
                            keys_to_delete.append(key)

                    # Remove expired entries from disk
                    if keys_to_delete:
                        for key in keys_to_delete:
                            try:
                                del shelf[key]
                            except KeyError:
                                pass
                        logger.debug(f"Pruned {len(keys_to_delete)} expired entries from {self._shelf_path}")

                self._stats.size = len(self._data)
            except Exception as e:
                logger.warning(f"Error loading cache from {self._shelf_path}: {e}")

    def sync_to_disk(self) -> None:
        """Sync in-memory cache to disk (called after every put)."""
        with self._lock:
            try:
                with shelve.open(self._shelf_path) as shelf:
                    # Update shelf with current data
                    for key, entry in self._data.items():
                        try:
                            shelf[key] = entry
                        except Exception as e:
                            logger.warning(f"Error syncing cache entry {key}: {e}")
            except Exception as e:
                logger.warning(f"Error syncing cache to {self._shelf_path}: {e}")

    def get(self, key: str) -> T | None:
        """Get a value by key, checking TTL expiry."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiry
            if entry.is_expired:
                del self._data[key]
                self._stats.misses += 1
                self._stats.size = len(self._data)
                # Try to remove from disk too
                try:
                    with shelve.open(self._shelf_path) as shelf:
                        if key in shelf:
                            del shelf[key]
                except Exception as e:
                    logger.debug(f"Error removing expired entry {key} from disk: {e}")
                return None

            # Move to end (most recently used) and record hit
            self._data.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1
            return entry.value

    def put(self, key: str, value: T, ttl: float | None = None) -> None:
        """Store a value with optional TTL override, syncing to disk."""
        with self._lock:
            if key in self._data:
                del self._data[key]
            elif len(self._data) >= self._max_size:
                evicted_key = next(iter(self._data))  # Get LRU key
                del self._data[evicted_key]
                self._stats.evictions += 1
                # Remove from disk too
                try:
                    with shelve.open(self._shelf_path) as shelf:
                        if evicted_key in shelf:
                            del shelf[evicted_key]
                except Exception as e:
                    logger.debug(f"Error removing evicted entry {evicted_key} from disk: {e}")

            self._data[key] = CacheEntry(
                value=value,
                created_at=time.monotonic(),
                ttl=ttl if ttl is not None else self._default_ttl,
            )
            self._stats.size = len(self._data)

            # Sync to disk immediately
            self.sync_to_disk()

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from memory and disk."""
        with self._lock:
            found_in_memory = key in self._data
            if found_in_memory:
                del self._data[key]
                self._stats.size = len(self._data)

            # Always try to remove from disk
            try:
                with shelve.open(self._shelf_path) as shelf:
                    if key in shelf:
                        del shelf[key]
                        found_in_memory = True
            except Exception as e:
                logger.debug(f"Error removing key {key} from disk: {e}")

            return found_in_memory

    def clear(self) -> None:
        """Clear all entries from memory and disk."""
        with self._lock:
            self._data.clear()
            self._stats.size = 0
            try:
                with shelve.open(self._shelf_path) as shelf:
                    shelf.clear()
            except Exception as e:
                logger.warning(f"Error clearing disk cache: {e}")


def _hash_key(*parts: str) -> str:
    """Create a deterministic cache key from multiple string parts."""
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


# ---- Specialized caches ----

# Embedding cache: disk-persisted cache for embeddings with 7-day TTL
# Survives process restarts and uses separate TTL from result cache
_embedding_cache: DiskLRUCache[list[float]] = DiskLRUCache(
    max_size=512,
    default_ttl=604800.0,  # 7 days
    path=os.path.expanduser("~/.docstruct/cache/embeddings"),
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
