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
import json
import os
from typing import Any
from core.config import Config


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
        self._history_file = Config.MEMORY_DIR / "history.jsonl"
        self._load_history()

    def _load_history(self):
        """Load persistent conversation history from file."""
        if not self._history_file.exists():
            return
            
        try:
            with open(self._history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Only keep the last max_turns
            for line in lines[-self._max_turns:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    turn = ConversationTurn(
                        role=data.get("role", "user"),
                        content=data.get("content", ""),
                        timestamp=data.get("timestamp", datetime.now().isoformat()),
                        metadata=data.get("metadata", {})
                    )
                    self._history.append(turn)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Failed to load history: {e}")

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> ConversationTurn:
        """Add a conversation turn to working RAM and persist to disk."""
        turn = ConversationTurn(role=role, content=content, metadata=metadata or {})
        with self._lock:
            self._history.append(turn)
            # Append to file
            try:
                with open(self._history_file, 'a', encoding='utf-8') as f:
                    record = {
                        "role": turn.role,
                        "content": turn.content,
                        "timestamp": turn.timestamp,
                        "metadata": turn.metadata
                    }
                    f.write(json.dumps(record) + '\n')
            except Exception:
                pass
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
        """Clear all conversation history in RAM and on disk."""
        with self._lock:
            self._history.clear()
            self._working_context.clear()
            try:
                if self._history_file.exists():
                    self._history_file.unlink()
            except Exception:
                pass

    def count(self) -> int:
        with self._lock:
            return len(self._history)
