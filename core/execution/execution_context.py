# core/execution/execution_context.py — Execution Context for SON V3
"""
Holds per-request execution metadata, session credentials, bounds and flags.
"""
from dataclasses import dataclass, field
import secrets
import time
from typing import Any, Dict, Optional


@dataclass
class ExecutionContext:
    """Execution context bound to an incoming action."""
    request_id: str = field(default_factory=lambda: f"exec_{secrets.token_hex(8)}")
    session_id: str = ""
    user_id: str = "primary_user"
    interface_type: str = "cli"        # cli, desktop_wpf, voice, whatsapp, automation
    working_directory: str = "C:\\AI"
    timeout_seconds: float = 30.0
    allow_shell: bool = True
    allow_elevation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout_seconds
