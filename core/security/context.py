# core/security/context.py — Trusted Security & Identity Context for SON V3
import time
import secrets
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from core.security.identity import identity_manager
from core.security.session_manager import session_manager
from core.security.audit_logger import audit_logger


VALID_INTERFACE_IDENTIFIERS = {
    "cli",
    "voice",
    "desktop",
    "desktop_gui",
    "whatsapp",
    "automation",
    "brain",
    "core_brain",
    "api",
    "router",
    "internet_agent",
    "desktop_agent",
    "test",
}


class SecurityContextError(ValueError):
    """Raised when security context is invalid, missing, unauthenticated, or mismatched."""
    pass


class SecurityContext(BaseModel):
    """
    Immutable, trusted security context generated solely by application code.
    Propagates authenticated identity, session, and tracing parameters through
    the entire orchestrator, agent, and tool execution pipeline.
    """
    user_id: str
    session_id: str
    request_id: str = Field(default_factory=lambda: f"req_{secrets.token_urlsafe(16)}")
    interface_type: str = "cli"  # "voice", "cli", "desktop", "whatsapp", "automation"
    interface: str = "cli"
    conversation_id: Optional[str] = None
    is_authenticated: bool = True
    created_at: float = Field(default_factory=time.time)
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync interface and interface_type
            if "interface" in data and "interface_type" not in data:
                data["interface_type"] = data["interface"]
            elif "interface_type" in data and "interface" not in data:
                data["interface"] = data["interface_type"]

            # Sync created_at and timestamp
            if "timestamp" in data and "created_at" not in data:
                data["created_at"] = data["timestamp"]
            elif "created_at" in data and "timestamp" not in data:
                data["timestamp"] = data["created_at"]

            # Sync metadata and request_metadata
            if "request_metadata" in data and "metadata" not in data:
                data["metadata"] = data["request_metadata"]
            elif "metadata" in data and "request_metadata" not in data:
                data["request_metadata"] = data["metadata"]
        return data

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise SecurityContextError("User ID must be a non-empty, authenticated identity string.")
        return v.strip()

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise SecurityContextError("Session ID must be a non-empty, trusted session identifier.")
        return v.strip()

    @field_validator("interface_type", "interface")
    @classmethod
    def validate_interface_type(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in VALID_INTERFACE_IDENTIFIERS:
            raise SecurityContextError(f"Security Error: Unknown or unauthorized interface identifier: '{v}'.")
        return clean

    def model_post_init(self, __context: Any) -> None:
        """Register session automatically in SessionManager upon creation if user is valid."""
        clean_uid = getattr(self, "user_id", "").strip()
        clean_sid = getattr(self, "session_id", "").strip()
        if clean_uid and clean_sid and identity_manager.is_valid_user(clean_uid):
            session_manager.register_session(
                session_id=clean_sid,
                user_id=clean_uid,
                interface_type=getattr(self, "interface_type", "cli"),
            )

    def validate_caller(self, authorized_users: set[str] | None = None) -> bool:
        """Enforces that caller is authenticated, recognized, and in authorized users."""
        if not self.is_authenticated:
            audit_logger.log_event(
                event_type="UNAUTHENTICATED_SECURITY_CONTEXT_BLOCKED",
                actor=self.user_id,
                session_id=self.session_id,
                status="BLOCKED",
            )
            raise SecurityContextError("Unauthenticated security context is rejected.")

        if not identity_manager.is_valid_user(self.user_id):
            audit_logger.log_event(
                event_type="IDENTITY_VALIDATION_FAILED",
                actor=self.user_id,
                session_id=self.session_id,
                status="BLOCKED",
                details={"reason": f"Unknown or inactive user '{self.user_id}'."},
            )
            raise SecurityContextError(f"User '{self.user_id}' is not authorized (not a recognized or active identity).")

        if authorized_users:
            canon = identity_manager.resolve_user_id(self.user_id) or self.user_id.lower()
            auth_set = {
                (identity_manager.resolve_user_id(u) or u.lower())
                for u in authorized_users
            }
            if canon not in auth_set and self.user_id.lower() not in {u.lower() for u in authorized_users}:
                audit_logger.log_event(
                    event_type="UNAUTHORIZED_USER_BLOCKED",
                    actor=self.user_id,
                    session_id=self.session_id,
                    status="BLOCKED",
                )
                raise SecurityContextError(f"User '{self.user_id}' is not authorized.")

        # Validate session lifecycle
        valid_sess, reason, _ = session_manager.validate_session(self.session_id, self.user_id)
        if not valid_sess:
            raise SecurityContextError(f"Session validation failed: {reason}")

        return True


# Typed RequestContext model reusing SecurityContext
class RequestContext(SecurityContext):
    """
    Typed request context model representing the full operational context
    for centralized orchestrator requests.
    """
    pass


def create_trusted_context(
    user_id: str = "primary_user",
    interface_type: str = "cli",
    session_id: str | None = None,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ttl_seconds: float | None = None,
) -> SecurityContext:
    """
    Factory function for trusted context creation in application interface layers.
    Never accepts client/LLM-controlled unverified values.
    Registers or generates an active cryptographically secure session.
    """
    clean_uid = (user_id or "").strip()
    if not clean_uid:
        raise SecurityContextError("User ID must be a non-empty string.")

    # Register/create session in SessionManager
    if session_id:
        sess = session_manager.register_session(
            session_id=session_id,
            user_id=clean_uid,
            interface_type=interface_type,
            ttl_seconds=ttl_seconds,
        )
        active_session_id = sess.session_id
    else:
        sess = session_manager.create_session(
            user_id=clean_uid,
            interface_type=interface_type,
            ttl_seconds=ttl_seconds,
        )
        active_session_id = sess.session_id

    meta = metadata or {}
    return SecurityContext(
        user_id=clean_uid,
        session_id=active_session_id,
        interface_type=interface_type,
        interface=interface_type,
        conversation_id=conversation_id,
        metadata=meta,
        request_metadata=meta,
    )


def create_request_context(
    user_id: str = "primary_user",
    interface: str = "cli",
    session_id: str | None = None,
    conversation_id: str | None = None,
    request_metadata: dict[str, Any] | None = None,
    ttl_seconds: float | None = None,
) -> RequestContext:
    """
    Convenience factory specifically producing typed RequestContext instances.
    """
    ctx = create_trusted_context(
        user_id=user_id,
        interface_type=interface,
        session_id=session_id,
        conversation_id=conversation_id,
        metadata=request_metadata,
        ttl_seconds=ttl_seconds,
    )
    return RequestContext(**ctx.model_dump())
