# memory.py — Persistent Memory & RAG (ChromaDB + Ollama Embeddings)
import time
import hashlib
from datetime import datetime

import chromadb
from ollama import embed

import config


class Memory:
    """
    Persistent semantic memory for SON.
    Uses ChromaDB for vector storage and Ollama nomic-embed-text for embeddings.
    Three collections: conversations, codebase, and facts.
    """

    def __init__(self):
        self._client = chromadb.PersistentClient(path=config.MEMORY_DIR)
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

    # ── Embedding ─────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        """Generate embedding using Ollama nomic-embed-text."""
        response = embed(model=self._embed_model, input=text)
        return response["embeddings"][0]

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
        timestamp = datetime.now().isoformat()

        # Upsert to avoid duplicates
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
        except Exception:
            pass

    # ── Codebase Memory ───────────────────────────────────────

    def store_code_chunk(self, chunk_id: str, content: str, metadata: dict):
        """Store a code chunk embedding."""
        embedding = self._embed(content)

        self._codebase.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
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
            # Get all IDs for this project and delete them
            all_data = self._codebase.get(
                where={"project": project},
            )
            if all_data["ids"]:
                self._codebase.delete(ids=all_data["ids"])
        else:
            # Delete entire collection and recreate
            self._client.delete_collection(config.COLLECTION_CODEBASE)
            self._codebase = self._client.get_or_create_collection(
                name=config.COLLECTION_CODEBASE,
                metadata={"hnsw:space": "cosine"},
            )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return memory statistics."""
        return {
            "conversations": self._conversations.count(),
            "codebase_chunks": self._codebase.count(),
            "facts": self._facts.count(),
        }
