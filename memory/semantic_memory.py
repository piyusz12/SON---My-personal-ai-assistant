# memory/semantic_memory.py — Persistent Semantic Memory & RAG (ChromaDB + Ollama Embeddings)
"""
L3 — Semantic Vector Memory:
Uses ChromaDB for vector storage and Ollama nomic-embed-text for embeddings.
Three collections: conversations, codebase, and facts.
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

try:
    from core.cache import EmbeddingCache
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False


class SemanticMemory:
    """
    Persistent semantic vector memory for SON (L3).
    """

    def __init__(self):
        self._client = chromadb.PersistentClient(path=config.MEMORY_DIR)
        self._ollama_client = ollama.Client(host=getattr(config, "OLLAMA_HOST", "http://localhost:11434"))
        self._embed_model = config.EMBED_MODEL
        self._max_results = config.MEMORY_MAX_RESULTS

        # Initialize collections
        _hnsw_params = {
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 128,
            "hnsw:search_ef": 50,
            "hnsw:M": 16,
        }
        self._conversations = self._client.get_or_create_collection(
            name=config.COLLECTION_CONVERSATIONS,
            metadata=_hnsw_params,
        )
        self._codebase = self._client.get_or_create_collection(
            name=config.COLLECTION_CODEBASE,
            metadata=_hnsw_params,
        )
        self._facts = self._client.get_or_create_collection(
            name=config.COLLECTION_FACTS,
            metadata=_hnsw_params,
        )

        self._embed_cache = EmbeddingCache(max_size_mb=2048) if _HAS_CACHE else None

    def _embed(self, text: str) -> list[float] | None:
        if self._embed_cache:
            cached = self._embed_cache.get(text)
            if cached is not None:
                return cached

        try:
            response = self._ollama_client.embed(model=self._embed_model, input=text)
            embedding = response["embeddings"][0]
            if self._embed_cache and embedding:
                self._embed_cache.put(text, embedding)
            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate embedding via Ollama: {e}")
            return None

    def _make_id(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def store_conversation(self, user_msg: str, assistant_msg: str):
        combined = f"User: {user_msg}\nSON: {assistant_msg}"
        doc_id = self._make_id(combined + str(time.time()))
        timestamp = datetime.now().isoformat()

        embedding = self._embed(combined)
        if embedding is None:
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
        n = n_results or self._max_results
        if self._conversations.count() == 0:
            return []

        if self._embed_cache:
            cached_result = self._embed_cache.get_cached_query(f"conv:{query}")
            if cached_result is not None:
                return cached_result

        query_embedding = self._embed(query)
        if query_embedding is None:
            return []

        results = self._conversations.query(
            query_embeddings=[query_embedding],
            n_results=min(n, self._conversations.count()),
        )

        docs = results["documents"][0] if results["documents"] else []
        if self._embed_cache and docs:
            self._embed_cache.cache_query_result(f"conv:{query}", docs)
        return docs

    def store_fact(self, fact: str, category: str = "general"):
        doc_id = self._make_id(fact)
        embedding = self._embed(fact)
        if embedding is None:
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

    def forget_fact(self, fact: str):
        doc_id = self._make_id(fact)
        try:
            self._facts.delete(ids=[doc_id])
        except Exception:
            pass

    def stats(self) -> dict:
        result = {
            "conversations": self._conversations.count(),
            "codebase_chunks": self._codebase.count(),
            "facts": self._facts.count(),
        }
        if self._embed_cache:
            result["embedding_cache"] = self._embed_cache.stats()
        return result


# Alias for backward compatibility
Memory = SemanticMemory
