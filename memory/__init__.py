# memory/__init__.py — SON V3 3-Layer Memory Package
"""
Unified 3-Layer Memory System:
- L1 RAM Memory (RAMMemory): Working dialogue context, recent turn deque
- L2 SQLite Memory (StructuredMemory): Persistent facts, user preferences, enrolled people, vision events
- L3 Vector Memory (SemanticMemory / Memory): ChromaDB vector search for long-term documents & conversations
- Coordinator (MemoryManager): Unified interface routing queries to appropriate layers
"""
from memory.ram_memory import RAMMemory, ConversationTurn
from memory.structured_memory import StructuredMemory
from memory.semantic_memory import SemanticMemory, Memory
from memory.manager import MemoryManager

__all__ = [
    "RAMMemory",
    "ConversationTurn",
    "StructuredMemory",
    "SemanticMemory",
    "Memory",
    "MemoryManager",
]
