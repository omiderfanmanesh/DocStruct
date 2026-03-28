"""Unit tests for caching layer."""

import os
import shutil
import tempfile
import time

import pytest

from docstruct.infrastructure.cache import (
    DiskLRUCache,
    LRUCache,
    cache_embedding,
    cache_result,
    clear_all_caches,
    get_all_cache_stats,
    get_cached_embedding,
    get_cached_result,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_all_caches()
    yield
    clear_all_caches()


class TestLRUCache:
    def test_put_and_get(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_returns_none(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        cache: LRUCache[str] = LRUCache(max_size=10, default_ttl=0.05, name="test")
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_custom_ttl_override(self):
        cache: LRUCache[str] = LRUCache(max_size=10, default_ttl=60.0, name="test")
        cache.put("key1", "value1", ttl=0.05)
        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        cache: LRUCache[str] = LRUCache(max_size=3, name="test")
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        cache.put("d", "4")  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == "2"

    def test_lru_access_order(self):
        cache: LRUCache[str] = LRUCache(max_size=3, name="test")
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        # Access "a" to make it most recently used
        cache.get("a")
        cache.put("d", "4")  # Should evict "b" (least recently used)
        assert cache.get("a") == "1"
        assert cache.get("b") is None

    def test_invalidate(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        cache.put("key1", "value1")
        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache.invalidate("key1") is False

    def test_clear(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        cache.put("a", "1")
        cache.put("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_stats(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        cache.put("a", "1")
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.size == 1
        assert stats.hit_rate == 0.5

    def test_update_existing_key(self):
        cache: LRUCache[str] = LRUCache(max_size=10, name="test")
        cache.put("key1", "old")
        cache.put("key1", "new")
        assert cache.get("key1") == "new"


class TestSpecializedCaches:
    def test_embedding_cache_round_trip(self):
        embedding = [0.1, 0.2, 0.3]
        cache_embedding("test query", "openai", "text-embedding-3-small", embedding)
        result = get_cached_embedding("test query", "openai", "text-embedding-3-small")
        assert result == embedding

    def test_embedding_cache_different_provider(self):
        embedding = [0.1, 0.2, 0.3]
        cache_embedding("test query", "openai", "text-embedding-3-small", embedding)
        # Different provider should miss
        assert get_cached_embedding("test query", "cohere", "embed-english-v3.0") is None

    def test_result_cache_round_trip(self):
        result = {"answer": "April 1", "citations": []}
        cache_result("When is the deadline?", "neo4j", result)
        cached = get_cached_result("When is the deadline?", "neo4j")
        assert cached == result

    def test_result_cache_different_backend(self):
        result = {"answer": "April 1"}
        cache_result("When is the deadline?", "neo4j", result)
        assert get_cached_result("When is the deadline?", "pageindex") is None

    def test_get_all_cache_stats(self):
        stats = get_all_cache_stats()
        assert "embedding" in stats
        assert "result" in stats
        assert "document_tree" in stats
        for name, cache_stats in stats.items():
            assert "hits" in cache_stats
            assert "hit_rate" in cache_stats


class TestDiskLRUCache:
    """Tests for DiskLRUCache with disk persistence."""

    def test_disk_persistence_across_instances(self):
        """Test that entries persist across two DiskLRUCache instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")

            # First instance: write data
            cache1: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)
            cache1.put("key1", "value1")
            cache1.put("key2", "value2")

            # Second instance: read same data from disk
            cache2: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)
            assert cache2.get("key1") == "value1"
            assert cache2.get("key2") == "value2"

    def test_ttl_expiry_on_load(self):
        """Test that expired entries are pruned on load_from_disk()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")

            # First instance: write data with short TTL
            cache1: DiskLRUCache[str] = DiskLRUCache(max_size=10, default_ttl=0.05, path=cache_path)
            cache1.put("key1", "value1")
            time.sleep(0.1)

            # Second instance: should not load expired entry
            cache2: DiskLRUCache[str] = DiskLRUCache(max_size=10, default_ttl=60.0, path=cache_path)
            assert cache2.get("key1") is None

    def test_ttl_expiry_on_get(self):
        """Test that expired entries are removed on get()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")
            cache: DiskLRUCache[str] = DiskLRUCache(max_size=10, default_ttl=0.05, path=cache_path)
            cache.put("key1", "value1")
            assert cache.get("key1") == "value1"
            time.sleep(0.1)
            assert cache.get("key1") is None

    def test_cross_model_key_isolation(self):
        """Test that different models have separate cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")
            cache: DiskLRUCache[list[float]] = DiskLRUCache(max_size=10, path=cache_path)

            # Simulate embedding cache usage with different models
            from docstruct.infrastructure.cache import _hash_key

            # Different providers/models should have different cache keys
            key1 = _hash_key("hello", "openai", "text-embedding-3-small")
            key2 = _hash_key("hello", "cohere", "embed-english-v3.0")

            assert key1 != key2, "Different models should produce different cache keys"

            # Store different values with different keys
            cache.put(key1, [0.1, 0.2, 0.3])
            cache.put(key2, [0.4, 0.5, 0.6])

            # Verify they remain isolated
            assert cache.get(key1) == [0.1, 0.2, 0.3]
            assert cache.get(key2) == [0.4, 0.5, 0.6]

    def test_lru_eviction_with_disk_sync(self):
        """Test LRU eviction with disk persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")
            cache: DiskLRUCache[str] = DiskLRUCache(max_size=3, path=cache_path)

            # Fill cache to max
            cache.put("a", "1")
            cache.put("b", "2")
            cache.put("c", "3")

            # Add one more, should evict "a" (LRU)
            cache.put("d", "4")

            # Verify in-memory state
            assert cache.get("a") is None
            assert cache.get("b") == "2"
            assert cache.get("c") == "3"
            assert cache.get("d") == "4"

            # Verify disk state in new instance
            cache2: DiskLRUCache[str] = DiskLRUCache(max_size=3, path=cache_path)
            assert cache2.get("a") is None
            assert cache2.get("b") == "2"
            assert cache2.get("c") == "3"
            assert cache2.get("d") == "4"

    def test_invalidate_removes_from_disk(self):
        """Test that invalidate() removes entries from both memory and disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")
            cache: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)

            cache.put("key1", "value1")
            assert cache.get("key1") == "value1"

            # Invalidate
            cache.invalidate("key1")
            assert cache.get("key1") is None

            # Verify removal from disk in new instance
            cache2: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)
            assert cache2.get("key1") is None

    def test_clear_removes_disk_data(self):
        """Test that clear() removes all data from both memory and disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "test_cache")
            cache: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)

            cache.put("key1", "value1")
            cache.put("key2", "value2")
            cache.clear()

            assert cache.get("key1") is None
            assert cache.get("key2") is None

            # Verify disk is cleared in new instance
            cache2: DiskLRUCache[str] = DiskLRUCache(max_size=10, path=cache_path)
            assert cache2.get("key1") is None
            assert cache2.get("key2") is None
