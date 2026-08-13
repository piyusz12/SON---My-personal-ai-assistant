# memory/structured_memory.py — L2 SQLite Structured Memory for SON V3
"""
L2 — Structured SQLite Memory:
Handles structured data, user preferences, facts, episodic vision events,
and local enrolled face biometric templates (opt-in only).

Schema:
- user_preferences: key-value configuration
- facts: persistent knowledge & user attributes
- enrolled_people: local biometric face embeddings for face recognition
- episodic_events: vision/system events (person entered, face recognized, tool executed)
- conversation_summaries: summarized historical chats
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import Config


class StructuredMemory:
    """
    L2 SQLite database manager for structured persistence.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_dir = Path(Config.MEMORY_DIR)
            db_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(db_dir / "son_structured.db")
        else:
            self._db_path = str(db_path)

        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize all relational tables."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # User Preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Persistent Facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT NOT NULL UNIQUE,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL
                )
            """)

            # Enrolled People for Local Face Recognition (Opt-in biometric database)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrolled_people (
                    person_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    samples_count INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1
                )
            """)

            # Episodic Vision & System Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Conversation Summaries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_topics TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

    # ── User Preferences ─────────────────────────────────────────

    def set_preference(self, key: str, value: Any):
        with self._lock, self._get_connection() as conn:
            val_str = json.dumps(value) if not isinstance(value, str) else value
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, val_str, now),
            )
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                val = row["value"]
                try:
                    return json.loads(val)
                except Exception:
                    return val
            return default

    # ── Facts ────────────────────────────────────────────────────

    def store_fact(self, fact: str, category: str = "general", confidence: float = 1.0):
        with self._lock, self._get_connection() as conn:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO facts (fact, category, confidence, created_at) VALUES (?, ?, ?, ?)",
                (fact.strip(), category, confidence, now),
            )
            conn.commit()

    def get_facts(self, category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT fact, category, confidence, created_at FROM facts WHERE category = ? ORDER BY id DESC LIMIT ?",
                    (category, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT fact, category, confidence, created_at FROM facts ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def delete_fact(self, fact: str) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM facts WHERE fact LIKE ?", (f"%{fact.strip()}%",))
            conn.commit()
            return cursor.rowcount > 0

    # ── Enrolled People (Face Recognition) ─────────────────────────

    def enroll_person(self, person_id: str, display_name: str, embedding: list[float], samples_count: int = 1):
        """Store or update a local biometric embedding for an enrolled person."""
        with self._lock, self._get_connection() as conn:
            now = datetime.now().isoformat()
            emb_json = json.dumps(embedding)
            conn.execute(
                """INSERT OR REPLACE INTO enrolled_people
                   (person_id, display_name, embedding_json, samples_count, created_at, enabled)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (person_id, display_name, emb_json, samples_count, now),
            )
            conn.commit()

    def get_enrolled_people(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        """Retrieve enrolled people with their biometric templates."""
        with self._lock, self._get_connection() as conn:
            if enabled_only:
                cursor = conn.execute(
                    "SELECT person_id, display_name, embedding_json, samples_count, created_at FROM enrolled_people WHERE enabled = 1"
                )
            else:
                cursor = conn.execute(
                    "SELECT person_id, display_name, embedding_json, samples_count, created_at, enabled FROM enrolled_people"
                )

            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["embedding"] = json.loads(d.pop("embedding_json"))
                results.append(d)
            return results

    def remove_person(self, person_id: str) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM enrolled_people WHERE person_id = ?", (person_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ── Episodic Events ───────────────────────────────────────────

    def log_event(self, event_type: str, details: dict[str, Any] | str):
        """Log an episodic event (e.g. vision detection, app launch, tool execution)."""
        with self._lock, self._get_connection() as conn:
            det_str = json.dumps(details) if isinstance(details, dict) else str(details)
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO episodic_events (event_type, details, timestamp) VALUES (?, ?, ?)",
                (event_type, det_str, now),
            )
            conn.commit()

    def get_recent_events(self, event_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            if event_type:
                cursor = conn.execute(
                    "SELECT event_type, details, timestamp FROM episodic_events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT event_type, details, timestamp FROM episodic_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            res = []
            for row in cursor.fetchall():
                d = dict(row)
                try:
                    d["details"] = json.loads(d["details"])
                except Exception:
                    pass
                res.append(d)
            return res

    # ── Conversation Summaries ────────────────────────────────────

    def store_summary(self, session_date: str, summary: str, key_topics: list[str] | None = None):
        with self._lock, self._get_connection() as conn:
            now = datetime.now().isoformat()
            topics_str = json.dumps(key_topics or [])
            conn.execute(
                "INSERT INTO conversation_summaries (session_date, summary, key_topics, created_at) VALUES (?, ?, ?, ?)",
                (session_date, summary, topics_str, now),
            )
            conn.commit()

    def get_recent_summaries(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT session_date, summary, key_topics, created_at FROM conversation_summaries ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
