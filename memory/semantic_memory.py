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
            "hnsw:search_ef": 64,
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

    def _embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float] | None]:
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self._ollama_client.embed(model=self._embed_model, input=batch)
                embeddings = response["embeddings"]
                results.extend(embeddings)
                
                if self._embed_cache:
                    for txt, emb in zip(batch, embeddings):
                        self._embed_cache.put(txt, emb)
            except Exception as e:
                logger.warning(f"Failed to generate batch embeddings via Ollama: {e}")
                results.extend([None] * len(batch))
        return results

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

    def store_code_chunk(self, chunk_id: str, content: str, metadata: dict):
        embedding = self._embed(content)
        if embedding is None:
            return
        
        self._codebase.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )

    def store_code_chunks_batch(self, chunks: list[dict], batch_size: int = 32):
        if not chunks:
            return
            
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self._embed_batch(texts, batch_size=batch_size)
        
        valid_ids, valid_embeddings, valid_documents, valid_metadatas = [], [], [], []
        
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is None:
                continue
            valid_ids.append(chunk["id"])
            valid_embeddings.append(embedding)
            valid_documents.append(chunk["content"])
            valid_metadatas.append(chunk.get("metadata", {}))
            
        if valid_ids:
            for i in range(0, len(valid_ids), 100):
                self._codebase.upsert(
                    ids=valid_ids[i:i+100],
                    embeddings=valid_embeddings[i:i+100],
                    documents=valid_documents[i:i+100],
                    metadatas=valid_metadatas[i:i+100]
                )

    def clear_codebase(self, project: str):
        try:
            self._codebase.delete(where={"project": project})
        except Exception:
            pass

    def query_code(self, question: str, n_results: int | None = None) -> list[dict]:
        n = n_results or self._max_results
        if self._codebase.count() == 0:
            return []
            
        if self._embed_cache:
            cached_result = self._embed_cache.get_cached_query(f"code:{question}")
            if cached_result is not None:
                return cached_result
                
        query_embedding = self._embed(question)
        if query_embedding is None:
            return []
            
        results = self._codebase.query(
            query_embeddings=[query_embedding],
            n_results=min(n, self._codebase.count()),
        )
        
        output = []
        if results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                output.append({
                    "content": doc,
                    "file": meta.get("file", "unknown"),
                    "start_line": meta.get("start_line", 0),
                    "end_line": meta.get("end_line", 0)
                })
        
        if self._embed_cache and output:
            self._embed_cache.cache_query_result(f"code:{question}", output)
        return output

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
