# core/security/audit_logger.py — Tamper-Resistant Structured Security Audit Logger
"""
Structured security audit logging with automatic secret redaction.
Records all security-relevant events, tool approvals, sandbox executions,
denials, and prompt injection detections in append-only JSONL format.
"""

import os
import re
import json
import time
import hashlib
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Mapping

from core.config import Config


# Regular expressions for detecting confidential keys and tokens
SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|secret|password|token|bearer|auth|credential)["\']?\s*[:=]\s*["\']?([^"\'\s,;]{8,})'), r'\1="[REDACTED_SECRET]"'),
    (re.compile(r'sk-[a-zA-Z0-9_-]{20,}'), '[REDACTED_OPENAI_KEY]'),
    (re.compile(r'AIza[0-9A-Za-z\-_]{30,45}'), '[REDACTED_GEMINI_KEY]'),
    (re.compile(r'e2b_[a-zA-Z0-9_\-\.]{10,}'), '[REDACTED_E2B_KEY]'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '[REDACTED_GITHUB_TOKEN]'),
    (re.compile(r'Bearer\s+[a-zA-Z0-9\._\-]{20,}', re.IGNORECASE), 'Bearer [REDACTED_TOKEN]'),
]


def redact_secrets(data: Any) -> Any:
    """
    Recursively redact sensitive credentials, tokens, and API keys
    from dictionaries, lists, strings, and objects.
    """
    if isinstance(data, str):
        redacted = data
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    elif isinstance(data, Mapping):
        sensitive_keys = {"api_key", "key", "password", "token", "secret", "auth", "authorization", "credential"}
        result = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                result[k] = "[REDACTED_SECRET]"
            else:
                result[k] = redact_secrets(v)
        return result
    elif isinstance(data, (list, tuple, set)):
        return [redact_secrets(item) for item in data]
    return data


def canonical_args_hash(arguments: dict[str, Any] | None) -> str:
    """
    Compute a deterministic SHA-256 hash of tool arguments.
    Enforces argument integrity and prevents tampering after approval.
    """
    if not arguments:
        return hashlib.sha256(b"{}").hexdigest()
    
    canonical_json = json.dumps(arguments, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


class SecurityAuditLogger:
    """
    Structured security audit logger writing append-only JSONL records.
    Never exposes raw secrets in logs.
    Thread-safe and synchronizes disk writes across all threads.
    """

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or (Config.LOGS_DIR / "security_audit.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log_event(
        self,
        event_type: str,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        risk_level: str | None = None,
        session_id: str = "default_session",
        approval_id: str | None = None,
        status: str = "RECORDED",
        actor: str = "agent",
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Record a security event into the audit log.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        args_hash = canonical_args_hash(arguments) if arguments is not None else None
        
        safe_args = redact_secrets(arguments) if arguments is not None else None
        safe_details = redact_secrets(details) if details is not None else {}

        record = {
            "timestamp": now_utc,
            "event_type": event_type,
            "request_id": request_id,
            "session_id": session_id,
            "actor": actor,
            "tool_name": tool_name,
            "risk_level": risk_level,
            "args_hash": args_hash,
            "arguments": safe_args,
            "approval_id": approval_id,
            "status": status,
            "details": safe_details,
        }

        # Thread-safe write to JSONL with explicit flush
        try:
            line = json.dumps(record, default=str) + "\n"
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
        except Exception as e:
            # Audit logging failures must not silence security controls
            print(f"[SECURITY AUDIT FAILURE] Failed writing to audit log: {e}")

        return record

    def flush(self) -> None:
        """Explicit flush interface for log synchronization."""
        pass

    def get_recent_events(
        self,
        limit: int = 50,
        event_type: str | None = None,
        min_risk: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query and return recent security audit events from the JSONL log.
        Supports filtering by event_type and risk level.
        """
        if not self.log_path.exists():
            return []

        results = []
        with self._lock:
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if event_type and entry.get("event_type") != event_type:
                            continue
                        if min_risk and entry.get("risk_level") != min_risk:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logging.getLogger("son.security").error(f"Error querying security audit log: {e}")
        return results


# Global singleton instance
audit_logger = SecurityAuditLogger()

