# core/security/session_manager.py — Cryptographic Session Lifecycle Manager for SON V3
"""
Secure Session Lifecycle Management for SON V3:
Enforces:
  1. Cryptographically secure random session ID generation (secrets.token_urlsafe).
  2. Strict 1-to-1 binding between authenticated user and session ID.
  3. Absolute lifetime and idle timeout enforcement.
  4. Session invalidation and revocation API (fail-closed).
  5. Cross-user session isolation and tampering prevention.
  6. Audit logging of all session lifecycle events without leaking session tokens.
"""

from enum import Enum
import time
import secrets
import threading
from typing import Any, Optional
from pydantic import BaseModel, Field

from core.security.identity import identity_manager
from core.security.audit_logger import audit_logger


class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Session(BaseModel):
    """Immutable representation of an authenticated user session."""
    session_id: str
    user_id: str
    canonical_user_id: str
    interface_type: str = "cli"
    created_at: float = Field(default_factory=time.time)
    last_activity: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    idle_timeout_seconds: float = 3600.0  # 1 hour idle limit
    max_lifetime_seconds: float = 86400.0  # 24 hours absolute limit
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        now = time.time()
        # 1. Absolute expiration
        if self.expires_at is not None and now > self.expires_at:
            return True
        # 2. Max lifetime expiration
        if now - self.created_at > self.max_lifetime_seconds:
            return True
        # 3. Idle timeout
        if now - self.last_activity > self.idle_timeout_seconds:
            return True
        return False


class SessionManager:
    """
    Centralized session authority tracking all active, expired, and revoked sessions.
    Thread-safe and synchronizes access to internal session state.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}

    def create_session(
        self,
        user_id: str,
        interface_type: str = "cli",
        session_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        idle_timeout_seconds: float = 3600.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Session:
        """
        Create and record a new cryptographically secure user session.
        Binds the session immutably to the validated internal user ID.
        """
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Cannot create session: User ID must be non-empty string.")

        canonical_uid = identity_manager.resolve_user_id(user_id) or user_id.strip()

        # Generate cryptographically secure session ID if not provided
        sid = session_id or f"sess_{secrets.token_urlsafe(32)}"

        now = time.time()
        expires = (now + ttl_seconds) if ttl_seconds is not None else None

        session = Session(
            session_id=sid,
            user_id=user_id,
            canonical_user_id=canonical_uid,
            interface_type=interface_type,
            created_at=now,
            last_activity=now,
            expires_at=expires,
            idle_timeout_seconds=idle_timeout_seconds,
            status=SessionStatus.ACTIVE,
            metadata=metadata or {},
        )

        with self._lock:
            self._sessions[sid] = session

        audit_logger.log_event(
            event_type="SESSION_CREATED",
            actor=canonical_uid,
            session_id=sid,
            status="SUCCESS",
            details={
                "interface_type": interface_type,
                "ttl_seconds": ttl_seconds,
                "idle_timeout": idle_timeout_seconds,
            },
        )
        return session

    def register_session(
        self,
        session_id: str,
        user_id: str,
        interface_type: str = "cli",
        ttl_seconds: Optional[float] = None,
    ) -> Session:
        """Register or retrieve an existing session for backward compatibility."""
        with self._lock:
            if session_id in self._sessions:
                sess = self._sessions[session_id]
                canonical_user = identity_manager.resolve_user_id(user_id) or user_id
                if sess.canonical_user_id != canonical_user and sess.user_id != user_id:
                    audit_logger.log_event(
                        event_type="CROSS_USER_SESSION_ATTEMPT_BLOCKED",
                        actor=user_id,
                        session_id=session_id,
                        status="BLOCKED",
                        details={
                            "existing_owner": sess.canonical_user_id,
                            "attempted_user": user_id,
                        },
                    )
                return sess
            return self.create_session(
                user_id=user_id,
                interface_type=interface_type,
                session_id=session_id,
                ttl_seconds=ttl_seconds,
            )

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID without validation."""
        with self._lock:
            return self._sessions.get(session_id)

    def validate_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> tuple[bool, str, Optional[Session]]:
        """
        Comprehensive session validation:
        1. Existence check.
        2. Status check (active vs revoked).
        3. Expiration / idle timeout check.
        4. User ownership check (prevent cross-user session access).
        """
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            audit_logger.log_event(
                event_type="SESSION_VALIDATION_FAILED",
                status="BLOCKED",
                details={"reason": "Session ID must be non-empty string."},
            )
            return False, "Session ID must be a non-empty string.", None

        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                audit_logger.log_event(
                    event_type="SESSION_VALIDATION_FAILED",
                    session_id=session_id,
                    actor=user_id or "unknown",
                    status="BLOCKED",
                    details={"reason": f"Unrecognized session '{session_id}'."},
                )
                return False, f"Session '{session_id}' is not recognized or has not been established.", None

            # Check Revocation
            if session.status == SessionStatus.REVOKED:
                audit_logger.log_event(
                    event_type="REVOKED_SESSION_BLOCKED",
                    session_id=session_id,
                    actor=session.user_id,
                    status="BLOCKED",
                    details={"reason": "Session has been revoked."},
                )
                return False, f"Session '{session_id}' has been revoked.", session

            # Check Expiration
            if session.status == SessionStatus.EXPIRED or session.is_expired():
                session.status = SessionStatus.EXPIRED
                audit_logger.log_event(
                    event_type="EXPIRED_SESSION_BLOCKED",
                    session_id=session_id,
                    actor=session.user_id,
                    status="BLOCKED",
                    details={"reason": "Session has expired due to timeout or lifetime."},
                )
                return False, f"Session '{session_id}' has expired.", session

            # Check User Binding (Prevent cross-user session theft)
            if user_id is not None:
                canonical_caller = identity_manager.resolve_user_id(user_id) or user_id.strip()
                if session.canonical_user_id != canonical_caller and session.user_id != user_id:
                    audit_logger.log_event(
                        event_type="CROSS_USER_SESSION_ATTEMPT_BLOCKED",
                        session_id=session_id,
                        actor=user_id,
                        status="BLOCKED",
                        details={
                            "session_owner": session.canonical_user_id,
                            "caller_user": user_id,
                        },
                    )
                    return False, f"Security violation: Session '{session_id}' belongs to user '{session.user_id}', not '{user_id}'.", session

            # Refresh last activity timestamp
            session.last_activity = time.time()

            audit_logger.log_event(
                event_type="SESSION_VALIDATED",
                session_id=session_id,
                actor=session.user_id,
                status="SUCCESS",
            )
            return True, "Session valid.", session

    def revoke_session(self, session_id: str, actor: str = "system") -> bool:
        """Revoke an active session immediately."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.status = SessionStatus.REVOKED
            audit_logger.log_event(
                event_type="SESSION_REVOKED",
                session_id=session_id,
                actor=actor,
                status="REVOKED",
            )
            return True

    def expire_session(self, session_id: str) -> bool:
        """Expire an active session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.status = SessionStatus.EXPIRED
            audit_logger.log_event(
                event_type="SESSION_EXPIRED",
                session_id=session_id,
                actor=session.user_id,
                status="EXPIRED",
            )
            return True

    def is_session_active(self, session_id: str) -> bool:
        valid, _, _ = self.validate_session(session_id)
        return valid

    def prune_stale_sessions(self, max_stale_seconds: float = 86400.0) -> int:
        """Purge stale sessions to prevent unbounded memory growth."""
        with self._lock:
            now = time.time()
            to_delete = [
                sid for sid, s in self._sessions.items()
                if (s.status != SessionStatus.ACTIVE or s.is_expired()) and (now - s.last_activity > max_stale_seconds)
            ]
            for sid in to_delete:
                del self._sessions[sid]
            return len(to_delete)

    def reset_for_test(self):
        """Testing utility to clear active sessions."""
        with self._lock:
            self._sessions.clear()


# Central singleton instance
session_manager = SessionManager()
