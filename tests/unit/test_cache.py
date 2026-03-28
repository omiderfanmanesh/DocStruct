"""Unit tests for caching layer."""

import time

import pytest

from docstruct.infrastructure.cache import (
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
