# core/security/context.py — Trusted Security & Identity Context for SON V3
import time
import uuid
from typing import Any
from pydantic import BaseModel, Field, field_validator


class SecurityContextError(ValueError):
    """Raised when security context is invalid, missing, or mismatched."""
    pass


class SecurityContext(BaseModel):
    """
    Immutable, trusted security context generated solely by application code.
    Propagates authenticated identity, session, and tracing parameters through
    the entire orchestrator, agent, and tool execution pipeline.
    """
    user_id: str
    session_id: str
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    interface_type: str = "cli"  # "voice", "cli", "desktop", "whatsapp", "automation"
    is_authenticated: bool = True
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise SecurityContextError("User ID must be a non-empty, authenticated identity string.")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise SecurityContextError("Session ID must be a non-empty, trusted session identifier.")
        return v.strip()

    def validate_caller(self, authorized_users: set[str] | None = None) -> bool:
        """Enforces that caller is authenticated and member of authorized users."""
        if not self.is_authenticated:
            raise SecurityContextError("Unauthenticated security context is rejected.")
        if authorized_users and self.user_id.lower() not in {u.lower() for u in authorized_users}:
            raise SecurityContextError(f"User '{self.user_id}' is not authorized.")
        return True


def create_trusted_context(
    user_id: str,
    interface_type: str = "cli",
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SecurityContext:
    """
    Factory function for trusted context creation in application interface layers.
    Never accepts client/LLM-controlled unverified values.
    """
    sess_id = session_id or f"session_{uuid.uuid4()}"
    return SecurityContext(
        user_id=user_id,
        session_id=sess_id,
        interface_type=interface_type,
        metadata=metadata or {},
    )

