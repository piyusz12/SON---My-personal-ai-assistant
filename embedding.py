# embedding.py — Embedding Utility (Cached + Batch Support)
# SON V3 — Optimized with LRU cache layer
"""
Changes from V2:
- LRU embedding cache integration
- Batch embedding support for multiple texts
- Singleton Ollama client to avoid connection overhead
"""
import ollama
import config

# Import caching layer (with fallback)
try:
    from core.cache import EmbeddingCache
    _cache = EmbeddingCache(max_size_mb=512)  # Smaller budget for standalone use
except ImportError:
    _cache = None

MODEL = getattr(config, "EMBED_MODEL", "nomic-embed-text")
_client = None


def _get_client():
    """Get or create singleton Ollama client."""
    global _client
    if _client is None:
        _client = ollama.Client(host=getattr(config, "OLLAMA_HOST", "http://localhost:11434"))
    return _client


def create_embedding(text: str) -> list[float] | None:
    """
    Create embedding for a single text.
    Results are cached to avoid redundant API calls.
    """
    # Check cache
    if _cache:
        cached = _cache.get(text)
        if cached is not None:
            return cached

    try:
        client = _get_client()
        response = client.embed(
            model=MODEL,
            input=text
        )
        embedding = response["embeddings"][0]

        # Store in cache
        if _cache and embedding:
            _cache.put(text, embedding)

        return embedding
    except Exception as e:
        print(f"Failed to create embedding: {e}")
        return None


def create_embeddings(texts: list[str]) -> list[list[float] | None]:
    """
    Batch embed multiple texts in a single Ollama API call.
    Reduces HTTP round-trip overhead for bulk operations.
    
    Args:
        texts: List of text strings to embed.
    
    Returns:
        List of embedding vectors (or None for failed embeddings).
    """
    if not texts:
        return []

    # Check cache for each text
    results = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    if _cache:
        for i, text in enumerate(texts):
            cached = _cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
    else:
        uncached_indices = list(range(len(texts)))
        uncached_texts = texts

    if not uncached_texts:
        return results

    try:
        client = _get_client()
        response = client.embed(
            model=MODEL,
            input=uncached_texts
        )
        embeddings = response["embeddings"]

        for idx, embedding in zip(uncached_indices, embeddings):
            results[idx] = embedding
            if _cache:
                _cache.put(texts[idx], embedding)

    except Exception as e:
        print(f"Batch embedding failed: {e}")
        # Fallback to sequential
        for idx, text in zip(uncached_indices, uncached_texts):
            results[idx] = create_embedding(text)

    return results


def get_cache_stats() -> dict | None:
    """Get embedding cache statistics."""
    if _cache:
        return _cache.stats()
    return None