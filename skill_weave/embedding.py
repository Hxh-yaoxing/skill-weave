"""Embedding layer — LRU cache + dual backend (Ollama bge-m3 / Dify API).

Zero new dependencies: stdlib only + requests (for Dify).
Backward-compatible: SkillRouter works unchanged when no new params are passed.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import OrderedDict
from typing import Optional

try:
    import requests
    _requests_available = True
except ImportError:
    _requests_available = False


# ─────────────────────────────────────────────────────────────────────
# LRU Embedding Cache
# ─────────────────────────────────────────────────────────────────────

class EmbeddingCache:
    """LRU cache for embedding vectors.

    Cache key = md5(text)
    Cache value = (embedding, timestamp)
    """

    def __init__(self, max_size: int = 500, ttl_seconds: Optional[float] = None):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[list[float], float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[list[float]]:
        key = self._key(text)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        emb, ts = entry
        if self._ttl is not None and (time.time() - ts) > self._ttl:
            # expired
            del self._cache[key]
            self._misses += 1
            return None
        # move to end (most-recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return emb

    def put(self, text: str, embedding: list[float]) -> None:
        key = self._key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = (embedding, time.time())
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)  # evict LRU
            self._cache[key] = (embedding, time.time())

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    @property
    def size(self) -> int:
        return len(self._cache)


# ─────────────────────────────────────────────────────────────────────
# Embedding Backends
# ─────────────────────────────────────────────────────────────────────

class OllamaEmbedBackend:
    """Embed via local Ollama /api/embed endpoint (bge-m3 by default)."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "bge-m3:latest"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed(self, text: str) -> list[float]:
        if not _requests_available:
            raise RuntimeError("requests not installed — cannot call Ollama API")
        resp = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if not embeddings:
            raise RuntimeError(f"Ollama returned empty embeddings: {data}")
        return embeddings[0]

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class SiliconFlowEmbedBackend:
    """Embed via SiliconFlow API (free tier, bge-m3)."""

    def __init__(self, base_url: str = "https://api.siliconflow.com/v1",
                 api_key: Optional[str] = None,
                 model: str = "BAAI/bge-m3"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        self.model = model

    def embed(self, text: str) -> list[float]:
        if not _requests_available:
            raise RuntimeError("requests not installed — cannot call SiliconFlow API")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json={"model": self.model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("data", [])
        if not embeddings:
            raise RuntimeError(f"SiliconFlow returned empty embeddings: {data}")
        return embeddings[0].get("embedding", [])

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models", 
                              headers={"Authorization": f"Bearer {self.api_key}"},
                              timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class DifyEmbedBackend:
    """Embed via Dify API (requires app with text-embedding configured).

    Note: Dify exposes embeddings through app-specific /v1/emebddings endpoints.
    Create a simple Text Embedding app in Dify, get its API key, and pass it here.
    For zero-setup embedding, use SiliconFlowEmbedBackend instead.
    """

    def __init__(self, base_url: str = "http://192.168.1.8:8090",
                 api_key: Optional[str] = None,
                 model: str = "BAAI/bge-m3"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("DIFY_API_KEY", "")
        self.model = model

    def embed(self, text: str) -> list[float]:
        if not _requests_available:
            raise RuntimeError("requests not installed — cannot call Dify API")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.base_url}/v1/embeddings",
            headers=headers,
            json={"model": self.model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("data", [])
        if not embeddings:
            raise RuntimeError(f"Dify returned empty embeddings: {data}")
        return embeddings[0].get("embedding", [])

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/v1/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class DualEmbedBackend:
    """Wraps primary + fallback backends with automatic failover.

    If primary.health_check() fails, falls back to secondary.
    Raises if both are unavailable.
    """

    def __init__(self, primary,
                 fallback=None):
        self.primary = primary
        self.fallback = fallback

    def embed(self, text: str) -> list[float]:
        if self.primary.health_check():
            return self.primary.embed(text)
        if self.fallback is not None and self.fallback.health_check():
            return self.fallback.embed(text)
        # last resort: try primary anyway (health check may be flaky)
        return self.primary.embed(text)

    def health_check(self) -> bool:
        if self.primary.health_check():
            return True
        if self.fallback is not None and self.fallback.health_check():
            return True
        return False


# ─────────────────────────────────────────────────────────────────────
# Factory helpers
# ─────────────────────────────────────────────────────────────────────

def create_embed_fn(
    backend: str = "ollama",
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "bge-m3:latest",
    dify_url: str = "http://192.168.1.8:8090",
    dify_api_key: Optional[str] = None,
    use_cache: bool = True,
    cache_size: int = 500,
) -> tuple[callable, Optional[EmbeddingCache]]:
    """Create an embed function with optional caching.

    Returns (embed_fn, cache) where cache is None if use_cache=False.
    """
    if backend == "ollama":
        be = OllamaEmbedBackend(ollama_url, ollama_model)
    elif backend == "siliconflow":
        be = SiliconFlowEmbedBackend(api_key=dify_api_key or None, model=ollama_model)
    elif backend == "dify":
        be = DifyEmbedBackend(dify_url, dify_api_key)
    elif backend == "dual":
        primary = OllamaEmbedBackend(ollama_url, ollama_model)
        fallback = SiliconFlowEmbedBackend(api_key=dify_api_key or None, model=ollama_model)
        be = DualEmbedBackend(primary, fallback)
    else:
        raise ValueError(f"Unknown backend: {backend!r}")

    cache = EmbeddingCache(max_size=cache_size) if use_cache else None

    def embed_fn(text: str) -> list[float]:
        if cache is not None:
            cached = cache.get(text)
            if cached is not None:
                return cached
        result = be.embed(text)
        if cache is not None:
            cache.put(text, result)
        return result

    return embed_fn, cache
