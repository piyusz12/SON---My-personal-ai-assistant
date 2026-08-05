# memory.py — Persistent Memory & RAG (ChromaDB + Ollama Embeddings)
# SON V3 — Optimized with embedding cache and batch support
"""
Changes from V2:
- LRU embedding cache (2GB) to skip re-embedding identical text
- Batch embedding support (_embed_batch) for multiple texts in one Ollama call
- Cache-aware recall and storage
"""
import time
import hashlib
from datetime import datetime
import logging
from core.config import Config
logger = Config.get_logger(__name__)

import chromadb
import ollama

import config

# Import caching layer (with fallback)
try:
    from core.cache import EmbeddingCache
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False


class Memory:
    """
    Persistent semantic memory for SON.
    Uses ChromaDB for vector storage and Ollama nomic-embed-text for embeddings.
    Three collections: conversations, codebase, and facts.
    """

    def __init__(self):
        self._client = chromadb.PersistentClient(path=config.MEMORY_DIR)
        self._ollama_client = ollama.Client(host=getattr(config, "OLLAMA_HOST", "http://localhost:11434"))
        self._embed_model = config.EMBED_MODEL
        self._max_results = config.MEMORY_MAX_RESULTS

        # Initialize collections
        self._conversations = self._client.get_or_create_collection(
            name=config.COLLECTION_CONVERSATIONS,
            metadata={"hnsw:space": "cosine"},
        )
        self._codebase = self._client.get_or_create_collection(
            name=config.COLLECTION_CODEBASE,
            metadata={"hnsw:space": "cosine"},
        )
        self._facts = self._client.get_or_create_collection(
            name=config.COLLECTION_FACTS,
            metadata={"hnsw:space": "cosine"},
        )

        # Embedding cache (LRU, ~2GB budget)
        self._embed_cache = EmbeddingCache(max_size_mb=2048) if _HAS_CACHE else None

    # ── Embedding (Cached) ────────────────────────────────────

    def _embed(self, text: str) -> list[float] | None:
        """
        Generate embedding using Ollama nomic-embed-text.
        Results are cached in RAM (LRU, 2GB budget) to avoid recomputation.
        """
        # Check cache first
        if self._embed_cache:
            cached = self._embed_cache.get(text)
            if cached is not None:
                return cached

        try:
            response = self._ollama_client.embed(model=self._embed_model, input=text)
            embedding = response["embeddings"][0]

            # Store in cache
            if self._embed_cache and embedding:
                self._embed_cache.put(text, embedding)

            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate embedding via Ollama: {e}")
            return None

    def _embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """
        Batch embed multiple texts in a single Ollama call.
        Reduces HTTP round-trip overhead for bulk operations.
        Falls back to sequential embedding if batch fails.
        """
        if not texts:
            return []

        # Check cache for each text
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        if self._embed_cache:
            for i, text in enumerate(texts):
                cached = self._embed_cache.get(text)
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

        # Batch embed uncached texts
        try:
            response = self._ollama_client.embed(
                model=self._embed_model,
                input=uncached_texts
            )
            embeddings = response["embeddings"]

            for idx, embedding in zip(uncached_indices, embeddings):
                results[idx] = embedding
                # Store in cache
                if self._embed_cache:
                    self._embed_cache.put(texts[idx], embedding)

        except Exception as e:
            logger.warning(f"Batch embedding failed, falling back to sequential: {e}")
            for idx, text in zip(uncached_indices, uncached_texts):
                results[idx] = self._embed(text)

        return results

    def _make_id(self, text: str) -> str:
        """Generate a deterministic ID from text content."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # ── Conversation Memory ───────────────────────────────────

    def store_conversation(self, user_msg: str, assistant_msg: str):
        """Store a conversation turn in long-term memory."""
        combined = f"User: {user_msg}\nSON: {assistant_msg}"
        doc_id = self._make_id(combined + str(time.time()))
        timestamp = datetime.now().isoformat()

        embedding = self._embed(combined)
        if embedding is None:
            logger.warning("Skipping store_conversation: Ollama embedding service unavailable.")
            return

        self._conversations.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[combined],
            metadatas=[{
                "timestamp": timestamp,
                "user_msg": user_msg[:500],
                "type": "conversation",
            }],
        )

    def recall(self, query: str, n_results: int | None = None) -> list[str]:
        """
        Retrieve relevant past conversations matching the query.

        Returns:
            List of conversation strings, most relevant first.
        """
        n = n_results or self._max_results

        if self._conversations.count() == 0:
            return []

        query_embedding = self._embed(query)
        if query_embedding is None:
            return []

        results = self._conversations.query(
            query_embeddings=[query_embedding],
            n_results=min(n, self._conversations.count()),
        )

        return results["documents"][0] if results["documents"] else []

    # ── Fact Memory ───────────────────────────────────────────

    def store_fact(self, fact: str, category: str = "general"):
        """Store a persistent fact (e.g., 'My name is Piyush')."""
        doc_id = self._make_id(fact)
        embedding = self._embed(fact)
        if embedding is None:
            logger.warning("Skipping store_fact: Ollama embedding service unavailable.")
            return
        timestamp = datetime.now().isoformat()

        self._facts.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[fact],
            metadatas=[{
                "timestamp": timestamp,
                "category": category,
                "type": "fact",
            }],
        )

    def recall_facts(self, query: str, n_results: int | None = None) -> list[str]:
        """Retrieve relevant facts."""
        n = n_results or self._max_results

        if self._facts.count() == 0:
            return []

        query_embedding = self._embed(query)
        if query_embedding is None:
            return []

        results = self._facts.query(
            query_embeddings=[query_embedding],
            n_results=min(n, self._facts.count()),
        )

        return results["documents"][0] if results["documents"] else []

    def forget_fact(self, fact: str):
        """Remove a specific fact from memory."""
        doc_id = self._make_id(fact)
        try:
            self._facts.delete(ids=[doc_id])
        except Exception as e:
            logger.error(f"Exception caught: {e}", exc_info=True)

    # ── Codebase Memory ───────────────────────────────────────

    def store_code_chunk(self, chunk_id: str, content: str, metadata: dict):
        """Store a code chunk embedding."""
        embedding = self._embed(content)
        if embedding is None:
            logger.warning("Skipping store_code_chunk: Ollama embedding service unavailable.")
            return

        self._codebase.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
        )

    def store_code_chunks_batch(self, chunks: list[dict]):
        """
        Batch store multiple code chunks with batch embedding.
        
        Each chunk: {"id": str, "content": str, "metadata": dict}
        """
        if not chunks:
            return

        texts = [c["content"] for c in chunks]
        embeddings = self._embed_batch(texts)

        # Filter out failed embeddings
        valid = [
            (c, e) for c, e in zip(chunks, embeddings) if e is not None
        ]

        if valid:
            self._codebase.upsert(
                ids=[c["id"] for c, _ in valid],
                embeddings=[e for _, e in valid],
                documents=[c["content"] for c, _ in valid],
                metadatas=[c["metadata"] for c, _ in valid],
            )

    def query_code(self, query: str, n_results: int | None = None) -> list[dict]:
        """
        Search codebase for relevant code chunks.

        Returns:
            List of dicts: [{"content": str, "file": str, ...}, ...]
        """
        n = n_results or self._max_results

        if self._codebase.count() == 0:
            return []

        query_embedding = self._embed(query)
        if query_embedding is None:
            return []

        results = self._codebase.query(
            query_embeddings=[query_embedding],
            n_results=min(n, self._codebase.count()),
        )

        output = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            output.append({
                "content": doc,
                "file": meta.get("file", "unknown"),
                "start_line": meta.get("start_line", 0),
                "project": meta.get("project", "unknown"),
            })

        return output

    def clear_codebase(self, project: str | None = None):
        """Clear codebase embeddings, optionally filtered by project."""
        if project:
            all_data = self._codebase.get(
                where={"project": project},
            )
            if all_data["ids"]:
                self._codebase.delete(ids=all_data["ids"])
        else:
            self._client.delete_collection(config.COLLECTION_CODEBASE)
            self._codebase = self._client.get_or_create_collection(
                name=config.COLLECTION_CODEBASE,
                metadata={"hnsw:space": "cosine"},
            )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return memory statistics."""
        result = {
            "conversations": self._conversations.count(),
            "codebase_chunks": self._codebase.count(),
            "facts": self._facts.count(),
        }
        # Add cache stats if available
        if self._embed_cache:
            result["embedding_cache"] = self._embed_cache.stats()
        return result
