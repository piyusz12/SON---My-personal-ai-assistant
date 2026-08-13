# memory/ram_memory.py — L1 RAM Fast Conversation Memory for SON V3
"""
L1 — RAM Memory:
Provides sub-millisecond access to recent conversation context,
working task state, and short-term dialogue turns.
Features automatic turn pruning and summarization trigger.
"""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import threading
from typing import Any


@dataclass
class ConversationTurn:
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {"role": self.role, "content": self.content}
        if "images" in self.metadata:
            d["images"] = self.metadata["images"]
        return d


class RAMMemory:
    """
    In-memory fast working memory (L1).
    Thread-safe deque storing recent turns for instant context retrieval.
    """

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._history: deque[ConversationTurn] = deque(maxlen=max_turns)
        self._lock = threading.RLock()
        self._working_context: dict[str, Any] = {}

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> ConversationTurn:
        """Add a conversation turn to working RAM."""
        turn = ConversationTurn(role=role, content=content, metadata=metadata or {})
        with self._lock:
            self._history.append(turn)
        return turn

    def get_recent_messages(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get formatted messages ready for LLM consumption."""
        with self._lock:
            turns = list(self._history)
            if limit and limit < len(turns):
                turns = turns[-limit:]
            return [t.to_dict() for t in turns]

    def set_working_context(self, key: str, value: Any):
        """Store transient task state (e.g. current active file or camera event)."""
        with self._lock:
            self._working_context[key] = value

    def get_working_context(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._working_context.get(key, default)

    def clear(self):
        """Clear all conversation history in RAM."""
        with self._lock:
            self._history.clear()
            self._working_context.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._history)
