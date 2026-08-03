# agents/memory_agent.py — Persistent Memory & Semantic RAG Agent for SON V3
from memory import Memory


class MemoryAgent:
    """
    Manages long-term conversation memory, persistent facts, and codebase vector storage via ChromaDB.
    """

    def __init__(self):
        self._memory = Memory()

    def store_fact(self, fact: str, category: str = "general"):
        self._memory.store_fact(fact, category=category)

    def recall_facts(self, query: str, limit: int = 5) -> list[str]:
        return self._memory.recall_facts(query, n_results=limit)

    def forget_fact(self, fact: str):
        self._memory.forget_fact(fact)

    def store_conversation(self, user_msg: str, assistant_reply: str):
        self._memory.store_conversation(user_msg, assistant_reply)

    def recall(self, query: str, limit: int = 5) -> list[str]:
        return self._memory.recall(query, n_results=limit)

    def stats(self) -> dict:
        return self._memory.stats()

    @property
    def raw_memory(self):
        return self._memory
