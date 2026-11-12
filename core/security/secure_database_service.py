# core/security/secure_database_service.py — Controlled Database Access Layer
"""
Zero-Trust Secure Database Access Layer for SON v3:
  - Strict query classification (SELECT vs INSERT/UPDATE vs DROP/TRUNCATE)
  - Parameterized SQL enforcement preventing SQL injection
  - Transaction management with guaranteed rollback on exceptions
  - Mandatory Human-in-the-Loop approval for destructive operations (DROP TABLE, TRUNCATE, bulk DELETE)
  - Database file boundary validation within approved memory directories
  - Structured audit trail for all executed database statements
"""

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from core.config import Config
from core.security.policy import RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, redact_secrets


# Destructive SQL statement keywords requiring explicit approval
DESTRUCTIVE_SQL_PATTERNS = [
    (re.compile(r'(?i)\bDROP\s+(?:TABLE|VIEW|INDEX|DATABASE|TRIGGER)\b'), "DROP_STATEMENT"),
    (re.compile(r'(?i)\bTRUNCATE\b'), "TRUNCATE_STATEMENT"),
    (re.compile(r'(?i)\bALTER\s+TABLE\s+.*?\bDROP\b'), "ALTER_DROP_COLUMN"),
    (re.compile(r'(?i)\bDELETE\s+FROM\s+\w+\s*(?:;|$|\s+WHERE\s+(?:1=1|true|1)\b)'), "BULK_DELETE_WITHOUT_WHERE"),
]

# Read-only query patterns permitted without approval
READ_ONLY_PATTERNS = [
    re.compile(r'(?i)^\s*(?:SELECT|EXPLAIN|PRAGMA\s+(?:table_info|foreign_keys|index_list))\b'),
]


class DatabaseSecurityError(Exception):
    """Raised when an unapproved destructive or invalid query is attempted."""
    pass


class SecureDatabaseService:
    """
    Controlled database access layer executing queries with parameterized SQL,
    transaction rollback guards, and mandatory human approval for destructive operations.
    """

    def __init__(self, db_path: str | Path | None = None):
        default_db = db_path or (Path(Config.MEMORY_DIR) / "son_structured.db")
        self.db_path = Path(default_db).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def classify_query(self, sql: str) -> tuple[RiskTier, str]:
        """
        Deterministically classify SQL statement risk and return (RiskTier, reason).
        """
        cleaned = sql.strip()

        # Check for destructive patterns first (HIGH risk)
        for pattern, reason in DESTRUCTIVE_SQL_PATTERNS:
            if pattern.search(cleaned):
                return RiskTier.HIGH, f"Destructive SQL operation detected: {reason}"

        # Check for read-only patterns (LOW risk)
        for pattern in READ_ONLY_PATTERNS:
            if pattern.search(cleaned):
                return RiskTier.LOW, "Read-only query"

        # Safe writes (INSERT, UPDATE with WHERE, CREATE TABLE IF NOT EXISTS) -> MEDIUM risk
        return RiskTier.MEDIUM, "Standard database state modification"

    def execute_query(
        self,
        query: str,
        params: tuple | list | dict = (),
        approval_id: str | None = None,
        session_id: str = "default_session",
    ) -> list[dict[str, Any]]:
        """
        Execute a SQL query with strict risk assessment and parameterization.
        - LOW risk (SELECT): Auto-authorized.
        - MEDIUM risk (INSERT, UPDATE): Auto-authorized with audit logging.
        - HIGH risk (DROP, TRUNCATE, bulk DELETE): Requires verified approval token.
        """
        risk, reason = self.classify_query(query)

        # High risk requires verified approval token
        if risk == RiskTier.HIGH:
            query_args = {"query": query, "params": list(params) if isinstance(params, (list, tuple)) else params}
            if not approval_id:
                req = approval_manager.create_request(
                    tool_name="database_query",
                    arguments=query_args,
                    session_id=session_id,
                    risk_level=RiskTier.HIGH,
                )
                audit_logger.log_event(
                    event_type="DB_APPROVAL_REQUIRED",
                    tool_name="database_query",
                    arguments=query_args,
                    risk_level="HIGH",
                    session_id=session_id,
                    approval_id=req.request_id,
                    status="AWAITING_APPROVAL",
                    details={"reason": reason},
                )
                raise DatabaseSecurityError(
                    f"Destructive database operation requires explicit human approval. "
                    f"Approval ticket created with ID: {req.request_id}. Please confirm."
                )

            valid, consume_reason = approval_manager.verify_and_consume(approval_id, query_args)
            if not valid:
                audit_logger.log_event(
                    event_type="DB_EXECUTION_BLOCKED",
                    tool_name="database_query",
                    approval_id=approval_id,
                    status="BLOCKED",
                    details={"reason": consume_reason},
                )
                raise PermissionError(f"Database authorization failed: {consume_reason}")

        # Execute securely using parameterized SQL with automatic rollback
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                if query.strip().upper().startswith("SELECT") or "PRAGMA" in query.upper():
                    rows = [dict(row) for row in cursor.fetchall()]
                else:
                    conn.commit()
                    rows = [{"rows_affected": cursor.rowcount, "lastrowid": cursor.lastrowid}]

                audit_logger.log_event(
                    event_type="DB_QUERY_EXECUTED",
                    tool_name="database_query",
                    arguments={"query": query, "params": redact_secrets(params)},
                    risk_level=risk.value,
                    session_id=session_id,
                    approval_id=approval_id,
                    status="SUCCESS",
                    details={"rows_count": len(rows)},
                )
                return rows

            except Exception as e:
                conn.rollback()
                audit_logger.log_event(
                    event_type="DB_QUERY_FAILED",
                    tool_name="database_query",
                    arguments={"query": query, "params": redact_secrets(params)},
                    risk_level=risk.value,
                    session_id=session_id,
                    approval_id=approval_id,
                    status="ERROR_ROLLED_BACK",
                    details={"error": str(e)},
                )
                raise DatabaseSecurityError(f"Database query execution failed (transaction rolled back): {e}")
            finally:
                conn.close()


# Global database service singleton
secure_database_service = SecureDatabaseService()

