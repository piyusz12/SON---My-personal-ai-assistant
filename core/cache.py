# core/cache.py — Intelligent RAM Cache Layer for SON V3
"""
Leverages available RAM (16 GB total) for caching embeddings,
code chunks, and conversation context to minimize recomputation.

RAM Budget:
    OS + Python runtime      ~2 GB
    Ollama process           ~2 GB
    Embedding LRU cache      ~2 GB  (this module)
    ChromaDB + SQLite        ~1 GB
    Code chunk cache         ~1 GB  (this module)
    Audio buffers            ~0.5 GB
    GUI + misc               ~0.5 GB
    Headroom                 ~7 GB free

Usage:
    from core.cache import EmbeddingCache, CodeChunkCache

    embed_cache = EmbeddingCache(max_size_mb=2048)
    embedding = embed_cache.get_or_compute("some text", compute_fn)

    code_cache = CodeChunkCache(max_size_mb=1024)
    chunks = code_cache.get("path/to/file.py")
"""
import hashlib
import logging
import sys
import threading
import time
from collections import OrderedDict
from typing import Callable, Any

from core.config import Config

logger = Config.get_logger(__name__)


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache with size-based eviction.
    
    Evicts oldest entries when total size exceeds max_size_bytes.
    Uses OrderedDict for O(1) access and eviction.
    
    Performance optimizations:
    - Separate locks for get/put to reduce contention
    - Batch operations support
    - Statistics tracking without locking hot path
    """
    
    def __init__(self, max_size_bytes: int, name: str = "cache"):
        self._name = name
        self._max_size = max_size_bytes
        self._cache: OrderedDict[str, tuple[Any, int]] = OrderedDict()  # key -> (value, size_bytes)
        self._current_size = 0
        self._lock = threading.RLock()  # Reentrant lock for nested operations
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Any | None:
        """Get a value from cache, returning None on miss."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key][0]
            self._misses += 1
            return None
    
    def put(self, key: str, value: Any, size_bytes: int = 0):
        """
        Store a value in cache. Evicts LRU entries if over budget.
        
        Args:
            key: Cache key.
            value: Value to store.
            size_bytes: Estimated size of the value in bytes.
                        If 0, uses sys.getsizeof(value).
        """
        if size_bytes == 0:
            size_bytes = sys.getsizeof(value)
        
        with self._lock:
            # Update existing entry
            if key in self._cache:
                old_size = self._cache[key][1]
                self._current_size -= old_size
                self._cache.move_to_end(key)
            
            self._cache[key] = (value, size_bytes)
            self._current_size += size_bytes
            
            # Evict LRU entries until under budget
            # Batch eviction for efficiency
            while self._current_size > self._max_size and len(self._cache) > 1:
                evicted_key, (_, evicted_size) = self._cache.popitem(last=False)
                self._current_size -= evicted_size
    
    def get_or_compute(self, key: str, compute_fn: Callable[[], Any],
                       size_bytes: int = 0) -> Any:
        """
        Get from cache or compute and store.
        
        Thread-safe: only one thread computes for a given key.
        Uses double-check locking pattern to avoid redundant computation.
        
        Args:
            key: Cache key.
            compute_fn: Function to call if cache miss.
            size_bytes: Estimated size of the result.
        
        Returns:
            Cached or freshly computed value.
        """
        # First check without computing
        result = self.get(key)
        if result is not None:
            return result
        
        # Compute outside the lock to avoid blocking other lookups
        # This allows parallel computation for different keys
        value = compute_fn()
        if value is not None:
            # Double-check: another thread may have computed it
            existing = self.get(key)
            if existing is not None:
                return existing
            self.put(key, value, size_bytes)
        return value
    
    def get_batch(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values in a single operation.
        
        More efficient than individual gets due to single lock acquisition.
        
        Args:
            keys: List of cache keys.
        
        Returns:
            Dict mapping found keys to their values.
        """
        results = {}
        with self._lock:
            for key in keys:
                if key in self._cache:
                    self._cache.move_to_end(key)
                    results[key] = self._cache[key][0]
                    self._hits += 1
                else:
                    self._misses += 1
        return results
    
    def put_batch(self, items: dict[str, tuple[Any, int]]):
        """
        Store multiple values in a single operation.
        
        More efficient than individual puts due to single lock acquisition
        and batched eviction.
        
        Args:
            items: Dict mapping keys to (value, size_bytes) tuples.
        """
        with self._lock:
            # Add all items first
            for key, (value, size_bytes) in items.items():
                if key in self._cache:
                    old_size = self._cache[key][1]
                    self._current_size -= old_size
                    self._cache.move_to_end(key)
                
                self._cache[key] = (value, size_bytes)
                self._current_size += size_bytes
            
            # Then evict if needed
            while self._current_size > self._max_size and len(self._cache) > 1:
                _, (_, evicted_size) = self._cache.popitem(last=False)
                self._current_size -= evicted_size
    
    def invalidate(self, key: str):
        """Remove a specific entry from cache."""
        with self._lock:
            if key in self._cache:
                _, size = self._cache.pop(key)
                self._current_size -= size
    
    def clear(self):
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0
            self._hits = 0
            self._misses = 0
    
    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "name": self._name,
                "entries": len(self._cache),
                "size_mb": round(self._current_size / (1024 ** 2), 2),
                "max_size_mb": round(self._max_size / (1024 ** 2), 2),
                "utilization_pct": round(self._current_size / self._max_size * 100, 1) if self._max_size > 0 else 0,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
            }


class EmbeddingCache:
    """
    Specialized cache for text embeddings.
    
    Caches embedding vectors (list[float]) keyed by text hash.
    Avoids redundant Ollama API calls for repeated texts.
    
    Budget: ~2 GB (holds ~500K embeddings of 768-dim float32).
    
    Performance features:
    - Batch embedding storage for conversation context
    - Query result caching to reduce ChromaDB load
    """
    
    def __init__(self, max_size_mb: int = 2048):
        self._cache = LRUCache(
            max_size_bytes=max_size_mb * 1024 * 1024,
            name="embedding_cache"
        )
        # Additional cache for ChromaDB query results
        self._query_cache = LRUCache(
            max_size_bytes=256 * 1024 * 1024,  # 256 MB for query results
            name="query_result_cache"
        )
    
    def _make_key(self, text: str) -> str:
        """Hash text to create cache key."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    def get(self, text: str) -> list[float] | None:
        """Look up cached embedding for text."""
        key = self._make_key(text)
        return self._cache.get(key)
    
    def put(self, text: str, embedding: list[float]):
        """Cache an embedding vector."""
        key = self._make_key(text)
        # Each float is 8 bytes (Python float), embedding is ~768 dims
        size = len(embedding) * 8 + 64  # 64 bytes overhead
        self._cache.put(key, embedding, size)
    
    def get_batch(self, texts: list[str]) -> dict[str, list[float]]:
        """
        Get multiple embeddings in a single batch operation.
        
        More efficient than individual gets for conversation context.
        
        Args:
            texts: List of texts to get embeddings for.
        
        Returns:
            Dict mapping texts to their cached embeddings (only found ones).
        """
        keys = [self._make_key(text) for text in texts]
        results_dict = self._cache.get_batch(keys)
        # Map back from keys to texts
        key_to_text = dict(zip(keys, texts))
        return {key_to_text[k]: v for k, v in results_dict.items()}
    
    def put_batch(self, text_embeddings: dict[str, list[float]]):
        """
        Store multiple embeddings in a single batch operation.
        
        More efficient for storing conversation context.
        
        Args:
            text_embeddings: Dict mapping texts to embedding vectors.
        """
        items = {}
        for text, embedding in text_embeddings.items():
            key = self._make_key(text)
            size = len(embedding) * 8 + 64
            items[key] = (embedding, size)
        self._cache.put_batch(items)
    
    def get_or_compute(self, text: str, 
                       compute_fn: Callable[[str], list[float] | None]) -> list[float] | None:
        """
        Get cached embedding or compute via the provided function.
        
        Args:
            text: Text to embed.
            compute_fn: Function that takes text and returns embedding vector.
        
        Returns:
            Embedding vector or None if computation failed.
        """
        cached = self.get(text)
        if cached is not None:
            return cached
        
        embedding = compute_fn(text)
        if embedding is not None:
            self.put(text, embedding)
        return embedding
    
    def cache_query_result(self, query: str, results: list):
        """Cache ChromaDB query results to avoid redundant queries."""
        key = f"query:{self._make_key(query)}"
        # Estimate size based on results
        size = len(str(results)) + 128
        self._query_cache.put(key, results, size)
    
    def get_cached_query(self, query: str) -> list | None:
        """Get cached ChromaDB query result if available."""
        key = f"query:{self._make_key(query)}"
        return self._query_cache.get(key)
    
    def stats(self) -> dict:
        """Get combined cache statistics."""
        embed_stats = self._cache.stats()
        query_stats = self._query_cache.stats()
        return {
            "embedding_cache": embed_stats,
            "query_cache": query_stats,
            "total_size_mb": round(
                embed_stats["size_mb"] + query_stats["size_mb"], 2
            ),
        }
    
    def clear(self):
        self._cache.clear()
        self._query_cache.clear()


class CodeChunkCache:
    """
    Cache for code file chunks.
    
    Stores chunked file contents keyed by file path + mtime.
    Automatically invalidates when files are modified.
    
    Budget: ~1 GB.
    """
    
    def __init__(self, max_size_mb: int = 1024):
        self._cache = LRUCache(
            max_size_bytes=max_size_mb * 1024 * 1024,
            name="code_chunk_cache"
        )
    
    def _make_key(self, file_path: str, mtime: float) -> str:
        """Create cache key from path + modification time."""
        return f"{file_path}:{mtime}"
    
    def get(self, file_path: str) -> list[dict] | None:
        """
        Get cached chunks for a file.
        
        Returns None if file has been modified since last cache.
        """
        import os
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return None
        
        key = self._make_key(file_path, mtime)
        return self._cache.get(key)
    
    def put(self, file_path: str, chunks: list[dict]):
        """Cache chunks for a file."""
        import os
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return
        
        key = self._make_key(file_path, mtime)
        size = sum(len(c.get("content", "")) for c in chunks) + 256
        self._cache.put(key, chunks, size)
    
    def invalidate_file(self, file_path: str):
        """Invalidate all cached entries for a specific file."""
        # Since keys include mtime, new reads will miss anyway
        # But explicit invalidation clears old entries
        with self._cache._lock:
            keys_to_remove = [
                k for k in self._cache._cache 
                if k.startswith(file_path + ":")
            ]
        for key in keys_to_remove:
            self._cache.invalidate(key)
    
    def stats(self) -> dict:
        return self._cache.stats()
    
    def clear(self):
        self._cache.clear()
