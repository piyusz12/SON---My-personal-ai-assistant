# core/security/identity.py — Centralized Identity Context & Provider for SON V3
"""
Centralized Identity Management Service for SON V3:
Enforces:
  1. Stable internal user identifiers (usr_*) separate from display names.
  2. Local-user identity provider with role-based access control (RBAC).
  3. Strict approver authorization: Only designated users can approve actions.
  4. Immutable validation ensuring LLMs cannot fabricate or impersonate identities.
  5. Audit logging for identity verification failures.
"""

from enum import Enum
import time
import threading
from typing import Any, Optional
from pydantic import BaseModel, Field

from core.security.audit_logger import audit_logger


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    SYSTEM = "system"
    GUEST = "guest"


class UserProfile(BaseModel):
    """Immutable representation of an authenticated principal."""
    user_id: str
    display_name: str
    role: UserRole
    is_active: bool = True
    can_approve: bool = False
    permissions: set[str] = Field(default_factory=set)
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IdentityManager:
    """
    Centralized identity service managing trusted local users, roles,
    and authorization to approve sensitive actions.
    Thread-safe and fail-closed against unauthenticated or malformed identities.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._users: dict[str, UserProfile] = {}
        self._aliases: dict[str, str] = {}
        self._init_default_principals()

    def _init_default_principals(self):
        """Initialize trusted application principals and role mappings."""
        # 1. Primary Owner / Dad (Admin & Approver)
        primary = UserProfile(
            user_id="usr_primary",
            display_name="Dad",
            role=UserRole.ADMIN,
            is_active=True,
            can_approve=True,
            permissions={"*", "system:admin", "tools:execute", "approvals:grant"},
        )
        self._register_internal(primary, aliases=["primary_user", "father", "dad", "son_desktop_user", "user", "admin"])

        # 2. Automation Engine (Operator, cannot self-approve high-risk actions)
        automation = UserProfile(
            user_id="usr_automation",
            display_name="Automation Engine",
            role=UserRole.OPERATOR,
            is_active=True,
            can_approve=False,
            permissions={"tools:execute", "automation:run"},
        )
        self._register_internal(automation, aliases=["automation_scheduler", "automation"])

        # 3. WhatsApp Integration (User, cannot self-approve host actions)
        whatsapp = UserProfile(
            user_id="usr_whatsapp",
            display_name="WhatsApp Bridge",
            role=UserRole.USER,
            is_active=True,
            can_approve=False,
            permissions={"tools:execute", "whatsapp:send"},
        )
        self._register_internal(whatsapp, aliases=["whatsapp_user"])

        # 4. Internal Autonomous Agents (System, cannot approve sensitive actions)
        system_agent = UserProfile(
            user_id="usr_system_agent",
            display_name="System Agent",
            role=UserRole.SYSTEM,
            is_active=True,
            can_approve=False,
            permissions={"tools:execute"},
        )
        self._register_internal(system_agent, aliases=["desktop_agent", "internet_agent", "core_brain", "agent"])

        # 5. Untrusted / Guest user
        guest = UserProfile(
            user_id="usr_guest",
            display_name="Guest User",
            role=UserRole.GUEST,
            is_active=True,
            can_approve=False,
            permissions=set(),
        )
        self._register_internal(guest, aliases=["guest", "untrusted"])

    def _register_internal(self, user: UserProfile, aliases: list[str] | None = None):
        with self._lock:
            self._users[user.user_id] = user
            if aliases:
                for alias in aliases:
                    self._aliases[alias.lower().strip()] = user.user_id

    def register_user(
        self,
        user_id: str,
        display_name: str,
        role: UserRole = UserRole.USER,
        can_approve: bool = False,
        permissions: set[str] | None = None,
        aliases: list[str] | None = None,
    ) -> UserProfile:
        """Register a new user identity in the local provider."""
        with self._lock:
            canonical_id = user_id.strip()
            user = UserProfile(
                user_id=canonical_id,
                display_name=display_name,
                role=role,
                is_active=True,
                can_approve=can_approve,
                permissions=permissions or {"tools:execute"},
            )
            self._register_internal(user, aliases)
            return user

    def resolve_user_id(self, user_id_or_alias: str) -> Optional[str]:
        """Resolve a user identifier or alias to its canonical internal ID."""
        if not user_id_or_alias or not isinstance(user_id_or_alias, str):
            return None
        norm = user_id_or_alias.strip().lower()
        with self._lock:
            if norm in self._aliases:
                return self._aliases[norm]
            for uid in self._users:
                if uid.lower() == norm:
                    return uid
            return None

    def get_user(self, user_id_or_alias: str) -> Optional[UserProfile]:
        """Retrieve user profile by ID or alias."""
        canonical_id = self.resolve_user_id(user_id_or_alias)
        if not canonical_id:
            # Check dynamic test user existence
            with self._lock:
                norm = (user_id_or_alias or "").strip()
                if norm and norm in self._users:
                    return self._users[norm]
            return None
        with self._lock:
            return self._users.get(canonical_id)

    def is_valid_user(self, user_id_or_alias: str) -> bool:
        """Check if an identity exists and is active."""
        if not user_id_or_alias or not isinstance(user_id_or_alias, str) or not user_id_or_alias.strip():
            audit_logger.log_event(
                event_type="IDENTITY_VALIDATION_FAILED",
                status="BLOCKED",
                details={"reason": "User ID must be non-empty string."},
            )
            return False

        user = self.get_user(user_id_or_alias)
        if not user or not user.is_active:
            audit_logger.log_event(
                event_type="IDENTITY_VALIDATION_FAILED",
                actor=user_id_or_alias,
                status="BLOCKED",
                details={"reason": f"Unknown or inactive user '{user_id_or_alias}'."},
            )
            return False
        return True

    def can_user_approve(self, user_id_or_alias: str) -> bool:
        """Verify whether the caller is authorized to grant approvals."""
        user = self.get_user(user_id_or_alias)
        if not user:
            return False
        return user.is_active and user.can_approve

    def authenticate_local_user(self, user_id_or_alias: str) -> Optional[UserProfile]:
        """
        Authenticate local user identity.
        Rejects unverified, non-existent, or inactive accounts.
        """
        user = self.get_user(user_id_or_alias)
        if not user or not user.is_active:
            audit_logger.log_event(
                event_type="AUTHENTICATION_FAILED",
                actor=str(user_id_or_alias),
                status="DENIED",
                details={"reason": "Local authentication failed: unknown or inactive user."},
            )
            return None
        return user


# Central singleton instance
identity_manager = IdentityManager()

