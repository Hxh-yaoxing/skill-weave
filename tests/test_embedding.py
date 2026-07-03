"""Tests for embedding layer — cache, backends, and SkillRouter integration."""

import sys
import os
import time
import math

# Ensure the parent package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skill_weave.embedding import (
    EmbeddingCache,
    OllamaEmbedBackend,
    SiliconFlowEmbedBackend,
    DifyEmbedBackend,
    DualEmbedBackend,
    create_embed_fn,
)
from skill_weave.router import SkillRouter


# ════════════════════════════════════════════════════════════════════
# 1. EmbeddingCache
# ════════════════════════════════════════════════════════════════════

class TestEmbeddingCache:
    """LRU cache tests: put→hit→miss→eviction→hit_rate."""

    def test_basic_put_get(self):
        cache = EmbeddingCache(max_size=10)
        emb = [0.1] * 1024
        cache.put("hello", emb)
        result = cache.get("hello")
        assert result == emb

    def test_miss(self):
        cache = EmbeddingCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        cache = EmbeddingCache(max_size=3)
        for i in range(4):
            cache.put(f"text{i}", [float(i)] * 4)
        # text0 should be evicted
        assert cache.get("text0") is None
        assert cache.get("text1") is not None
        assert cache.get("text2") is not None
        assert cache.get("text3") is not None

    def test_lru_order_maintenance(self):
        cache = EmbeddingCache(max_size=3)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])
        # access "a" to make it recently used
        cache.get("a")
        # add "d" — should evict "b" (least recently used)
        cache.put("d", [4.0])
        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("d") is not None

    def test_hit_rate(self):
        cache = EmbeddingCache(max_size=10)
        cache.put("x", [1.0])
        cache.get("x")   # hit
        cache.get("x")   # hit
        cache.get("y")   # miss
        assert abs(cache.hit_rate - 2 / 3) < 1e-9

    def test_hit_rate_empty(self):
        cache = EmbeddingCache(max_size=10)
        assert cache.hit_rate == 0.0

    def test_ttl_expiration(self):
        cache = EmbeddingCache(max_size=10, ttl_seconds=0.1)
        cache.put("key", [42.0])
        assert cache.get("key") is not None
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_clear(self):
        cache = EmbeddingCache(max_size=10)
        cache.put("a", [1.0])
        cache.get("a")
        cache.clear()
        assert cache.get("a") is None
        assert cache.size == 0

    def test_update_existing_key(self):
        cache = EmbeddingCache(max_size=10)
        cache.put("k", [1.0])
        cache.put("k", [2.0])
        assert cache.get("k") == [2.0]
        assert cache.size == 1


# ════════════════════════════════════════════════════════════════════
# 2. OllamaEmbedBackend
# ════════════════════════════════════════════════════════════════════

class TestOllamaBackend:
    """Test against local Ollama instance."""

    def test_health_check(self):
        be = OllamaEmbedBackend()
        # Ollama runs locally, should be reachable
        healthy = be.health_check()
        print(f"  Ollama health_check: {healthy}")
        assert isinstance(healthy, bool)

    def test_embed_real(self):
        be = OllamaEmbedBackend()
        if not be.health_check():
            print("  SKIP: Ollama not running locally")
            return
        emb = be.embed("Hello world")
        assert isinstance(emb, list)
        assert len(emb) > 100  # bge-m3 produces 1024-dim vectors
        assert all(isinstance(x, float) for x in emb[:5])


# ════════════════════════════════════════════════════════════════════
# 2.5. SiliconFlowEmbedBackend (unit tests, no API calls)
# ════════════════════════════════════════════════════════════════════

class TestSiliconFlowBackend:
    """Unit tests for SiliconFlow embedding backend."""

    def test_default_url_and_model(self):
        be = SiliconFlowEmbedBackend(api_key="sk-test")
        assert be.base_url == "https://api.siliconflow.com/v1"
        assert be.model == "BAAI/bge-m3"

    def test_custom_model(self):
        be = SiliconFlowEmbedBackend(api_key="sk-test", model="Pro/BAAI/bge-m3")
        assert be.model == "Pro/BAAI/bge-m3"

    def test_health_check_fails_no_key(self):
        be = SiliconFlowEmbedBackend(api_key="")
        assert be.health_check() is False


# ════════════════════════════════════════════════════════════════════
# 3. DualEmbedBackend (mock-based)
# ════════════════════════════════════════════════════════════════════

class _MockBackend:
    """Lightweight mock for testing DualEmbedBackend."""

    def __init__(self, healthy: bool = True, result: list[float] | None = None):
        self._healthy = healthy
        self._result = result or [0.5] * 10

    def embed(self, text: str) -> list[float]:
        return self._result

    def health_check(self) -> bool:
        return self._healthy


class TestDualEmbedBackend:
    """Test primary/fallback logic with mock backends."""

    def test_primary_available(self):
        primary = _MockBackend(healthy=True, result=[1.0] * 10)
        fallback = _MockBackend(healthy=True, result=[2.0] * 10)
        dual = DualEmbedBackend(primary, fallback)
        assert dual.embed("test") == [1.0] * 10

    def test_primary_down_fallback_available(self):
        primary = _MockBackend(healthy=False, result=[1.0] * 10)
        fallback = _MockBackend(healthy=True, result=[2.0] * 10)
        dual = DualEmbedBackend(primary, fallback)
        assert dual.embed("test") == [2.0] * 10

    def test_both_down_tries_primary_anyway(self):
        primary = _MockBackend(healthy=False, result=[1.0] * 10)
        fallback = _MockBackend(healthy=False, result=[2.0] * 10)
        dual = DualEmbedBackend(primary, fallback)
        # Should still try primary (last resort)
        assert dual.embed("test") == [1.0] * 10

    def test_no_fallback(self):
        primary = _MockBackend(healthy=True)
        dual = DualEmbedBackend(primary, fallback=None)
        assert dual.embed("test") == [0.5] * 10

    def test_health_check(self):
        primary = _MockBackend(healthy=False)
        fallback = _MockBackend(healthy=True)
        dual = DualEmbedBackend(primary, fallback)
        assert dual.health_check() is True

    def test_health_check_both_down(self):
        primary = _MockBackend(healthy=False)
        fallback = _MockBackend(healthy=False)
        dual = DualEmbedBackend(primary, fallback)
        assert dual.health_check() is False


# ════════════════════════════════════════════════════════════════════
# 4. SkillRouter integration with cache
# ════════════════════════════════════════════════════════════════════

def _make_counter_embed_fn():
    """Create a counting embed_fn to verify caching behavior."""
    call_count = {"n": 0}

    def embed_fn(text: str) -> list[float]:
        call_count["n"] += 1
        # Simple deterministic: hash-based pseudo-embedding
        h = hash(text)
        return [float((h >> i) & 1) for i in range(16)]

    return embed_fn, call_count


class TestSkillRouterCache:
    """Verify SkillRouter uses EmbeddingCache correctly."""

    def test_register_and_route_uses_cache(self):
        embed_fn, counter = _make_counter_embed_fn()
        router = SkillRouter(embed_fn=embed_fn, cache_size=50)

        router.register_skill("git", metadata="version control git commits")
        router.register_skill("docker", metadata="container deployment docker")

        # register_skill calls embed_fn for each
        assert counter["n"] == 2

        # route with a new task — should call embed_fn once
        results1 = router.route("deploy container to server", top_k=2)
        assert len(results1) > 0
        calls_after_first_route = counter["n"]

        # route with SAME task — should use cache, no new embed_fn call
        results2 = router.route("deploy container to server", top_k=2)
        assert counter["n"] == calls_after_first_route, "Cache hit should not call embed_fn"
        assert len(results2) > 0

    def test_backward_compat_no_cache(self):
        """Without embed_fn, everything still works (keyword fallback)."""
        router = SkillRouter()
        router.register_skill("git", metadata="version control")
        results = router.route("git commit", top_k=1)
        assert len(results) > 0

    def test_cache_size_parameter(self):
        embed_fn, _ = _make_counter_embed_fn()
        router = SkillRouter(embed_fn=embed_fn, cache_size=100)
        assert router._cache is not None
        assert router._cache._max_size == 100

    def test_cache_size_zero_disables(self):
        """cache_size=0 should still create cache but with max_size=0."""
        embed_fn, _ = _make_counter_embed_fn()
        router = SkillRouter(embed_fn=embed_fn, cache_size=0)
        # cache exists but is effectively no-op
        assert router._cache is not None


# ════════════════════════════════════════════════════════════════════
# 5. create_embed_fn factory
# ════════════════════════════════════════════════════════════════════

class TestCreateEmbedFn:
    """Test the factory function."""

    def test_ollama_factory(self):
        fn, cache = create_embed_fn(backend="ollama", use_cache=True, cache_size=50)
        assert callable(fn)
        assert isinstance(cache, EmbeddingCache)

    def test_no_cache_factory(self):
        fn, cache = create_embed_fn(backend="ollama", use_cache=False)
        assert cache is None

    def test_siliconflow_factory(self):
        fn, cache = create_embed_fn(backend="siliconflow", use_cache=False)
        assert callable(fn)

    def test_dual_factory(self):
        fn, cache = create_embed_fn(backend="dual", use_cache=False)
        assert callable(fn)

    def test_invalid_backend(self):
        try:
            create_embed_fn(backend="nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


# ════════════════════════════════════════════════════════════════════
# Runner
# ════════════════════════════════════════════════════════════════════

def _run_tests():
    """Minimal test runner (no pytest dependency)."""
    passed = 0
    failed = 0
    errors = []

    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue
        instance = cls()
        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            test_name = f"{cls_name}.{method_name}"
            try:
                getattr(instance, method_name)()
                print(f"  ✅ {test_name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {test_name}: {e}")
                failed += 1
                errors.append((test_name, e))

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        for name, err in errors:
            print(f"  FAIL: {name} — {err}")
    return failed == 0


if __name__ == "__main__":
    success = _run_tests()
    sys.exit(0 if success else 1)
