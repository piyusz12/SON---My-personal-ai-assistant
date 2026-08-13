# memory/manager.py — Unified 3-Layer Memory Manager for SON V3
"""
3-Layer Memory System Architecture:
  L1: RAM (Working conversation context, recent dialogue deque, fast context)
  L2: SQLite (Structured facts, preferences, episodic events, enrolled people)
  L3: ChromaDB (Semantic vector search for deep documents, past chats, codebase)

MemoryManager orchestrates all three layers based on request intent:
- COMMAND: Bypasses memory search completely (<1ms)
- CHAT: Retrieves L1 recent context + relevant L2 facts (<5ms)
- COMPLEX: Performs full RAG (L1 + L2 + L3 semantic search)
"""
from typing import Any
from memory.ram_memory import RAMMemory
from memory.structured_memory import StructuredMemory


class MemoryManager:
    """
    Unified manager orchestrating L1, L2, and L3 memory layers.
    """

    def __init__(self, semantic_memory=None):
        self.ram = RAMMemory(max_turns=12)
        self.structured = StructuredMemory()
        self.semantic = semantic_memory  # L3 ChromaDB instance (or loaded on demand)

    def attach_semantic_memory(self, semantic_memory):
        self.semantic = semantic_memory

    # ── Context Building ─────────────────────────────────────────

    def build_context(self, user_message: str, include_semantic: bool = True) -> str:
        """
        Build context string tailored to query complexity.
        """
        context_blocks = []

        # 1. Facts from L2 Structured DB
        facts = self.structured.get_facts(limit=5)
        if facts:
            fact_lines = "\n".join(f"- {f['fact']}" for f in facts)
            context_blocks.append(f"[KNOWN FACTS & PREFERENCES]\n{fact_lines}")

        # 2. Semantic Recall from L3 (if requested and available)
        if include_semantic and self.semantic:
            try:
                memories = self.semantic.recall(user_message, n_results=3)
                if memories:
                    mem_lines = "\n".join(f"- {m}" for m in memories)
                    context_blocks.append(f"[RELEVANT HISTORICAL CONTEXT]\n{mem_lines}")
            except Exception:
                pass

        # 3. Recent episodic events (e.g. recent vision/camera detection)
        recent_events = self.structured.get_recent_events(limit=3)
        if recent_events:
            event_lines = "\n".join(f"- [{e['timestamp'][11:19]}] {e['event_type']}: {e['details']}" for e in recent_events)
            context_blocks.append(f"[RECENT SYSTEM & VISION EVENTS]\n{event_lines}")

        return "\n\n".join(context_blocks) if context_blocks else ""

    # ── Recording Interactions ───────────────────────────────────

    def record_turn(self, user_message: str, assistant_reply: str):
        """Save dialogue turn into L1 RAM and asynchronously into L3 Semantic DB."""
        # 1. L1 RAM
        self.ram.add_turn("user", user_message)
        self.ram.add_turn("assistant", assistant_reply)

        # 2. L3 Semantic vector persistence
        if self.semantic:
            try:
                self.semantic.store_conversation(user_message, assistant_reply)
            except Exception:
                pass

    # ── Facts & Preferences ──────────────────────────────────────

    def remember_fact(self, fact: str, category: str = "general"):
        self.structured.store_fact(fact, category=category)
        if self.semantic:
            try:
                self.semantic.store_fact(fact, category=category)
            except Exception:
                pass

    def forget_fact(self, fact: str) -> bool:
        res = self.structured.delete_fact(fact)
        if self.semantic:
            try:
                self.semantic.forget_fact(fact)
            except Exception:
                pass
        return res

    def get_facts(self) -> list[dict[str, Any]]:
        return self.structured.get_facts()

    # ── Statistics ────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        stats = {
            "ram_turns": self.ram.count(),
            "facts_count": len(self.structured.get_facts(limit=1000)),
            "enrolled_people": len(self.structured.get_enrolled_people(enabled_only=False)),
        }
        if self.semantic:
            try:
                stats.update(self.semantic.stats())
            except Exception:
                pass
        return stats
