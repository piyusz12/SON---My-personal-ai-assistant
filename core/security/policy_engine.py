# core/security/policy_engine.py — Centralized Zero-Trust Security Policy Engine
"""
Deterministic Security Policy Engine for SON v3:
  Answers all authorization questions:
    - Is this tool authorized?
    - Is this user authorized?
    - Is this operation permitted?
    - What is the risk level?
    - Is human approval required?
    - Is approval valid?
    - Are the arguments unchanged?
    - Is the operation expired?
    - Should the request be denied?

Every sensitive operation passes through this engine.
Uses strictly deterministic application code — NEVER language model heuristics.
"""

from typing import Any
from pydantic import BaseModel, Field

from core.security.policy import RiskTier, classify_risk
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger, canonical_args_hash, redact_secrets
from core.security.identity import identity_manager


class PolicyDecision(BaseModel):
    """Deterministic evaluation outcome for an action."""
    allowed: bool
    risk_tier: RiskTier
    requires_approval: bool
    reason: str
    approval_id: str | None = None
    sanitized_arguments: dict[str, Any] = Field(default_factory=dict)


class SecurityPolicyEngine:
    """
    Centralized zero-trust security policy service evaluating authorization,
    permission scoping, argument integrity, and cryptographic approval tokens.
    """

    def __init__(self, authorized_users: set[str] | None = None):
        self._authorized_users = authorized_users or {
            "primary_user",
            "son_desktop_user",
            "user",
            "dad",
            "father",
            "usr_primary",
            "usr_admin",
            "admin",
            "usr_automation",
            "automation_scheduler",
            "automation",
            "usr_whatsapp",
            "whatsapp_user",
            "usr_system_agent",
            "desktop_agent",
            "internet_agent",
            "core_brain",
            "agent",
            "alice",
            "bob",
            "test_user",
        }
        # Permitted tools allowlist
        self._authorized_tools = {
            "execute_python_code",
            "execute_sandbox_command",
            "read_file",
            "write_file",
            "delete_path",
            "search_files",
            "move_file",
            "list_directory",
            "open_application",
            "close_application",
            "set_volume",
            "set_brightness",
            "shutdown_pc",
            "restart_pc",
            "web_search",
            "read_webpage",
            "get_weather",
            "get_news",
            "fetch_webpage",
            "docker_list_containers",
            "docker_start_container",
            "docker_stop_container",
            "docker_start",
            "docker_stop",
            "docker_restart",
            "run_routine",
            "list_routines",
            "create_routine",
            "delete_routine",
            "database_query",
            "secure_file_delete",
            "get_system_info",
            "take_screenshot",
            "send_whatsapp_message",
            "create_whatsapp_draft",
            "open_whatsapp_draft",
            "open_website",
            "search_website",
            "type_message",
            "send_web_message",
            "list_open_windows",
        }

    def is_user_authorized(self, user_id: str, session_id: str = "default_session") -> bool:
        """Validate whether caller identity is authorized for system operations."""
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            return False
        clean_uid = user_id.strip()
        canon = identity_manager.resolve_user_id(clean_uid) or clean_uid.lower()
        if clean_uid.lower() not in self._authorized_users and canon not in self._authorized_users:
            audit_logger.log_event(
                event_type="UNAUTHORIZED_USER_BLOCKED",
                actor=user_id,
                session_id=session_id,
                status="BLOCKED",
                details={"reason": "User not in authorized desktop users set"},
            )
            return False
        return True

    def is_tool_authorized(self, tool_name: str) -> bool:
        """Verify whether the requested tool exists in the application-approved allowlist."""
        return tool_name in self._authorized_tools

    def classify_risk(self, tool_name: str, arguments: dict[str, Any]) -> RiskTier:
        """Deterministically determine the operation risk tier."""
        return classify_risk(tool_name, arguments)

    def requires_human_approval(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Check if action requires explicit human authorization."""
        risk = self.classify_risk(tool_name, arguments)
        return risk == RiskTier.HIGH

    def verify_approval(
        self,
        approval_id: str,
        arguments: dict[str, Any],
        tool_name: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> tuple[bool, str]:
        """
        Verify that an approval token exists, is approved, is not expired,
        and matches the exact argument hash, tool, session, and user.
        """
        return approval_manager.verify_and_consume(
            approval_id,
            arguments,
            tool_name=tool_name,
            session_id=session_id,
            user_id=user_id,
        )

    def evaluate_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: str = "primary_user",
        session_id: str = "default_session",
        approval_id: str | None = None,
    ) -> PolicyDecision:
        """
        Comprehensive zero-trust evaluation answering all policy questions:
        Returns PolicyDecision(allowed=True/False, ...).
        """
        # 1. User authorization check
        if not self.is_user_authorized(user_id, session_id):
            return PolicyDecision(
                allowed=False,
                risk_tier=RiskTier.HIGH,
                requires_approval=False,
                reason=f"User '{user_id}' is not authorized to invoke tools.",
                sanitized_arguments=redact_secrets(arguments),
            )

        # 2. Tool allowlist check
        if not self.is_tool_authorized(tool_name):
            audit_logger.log_event(
                event_type="UNREGISTERED_TOOL_BLOCKED",
                tool_name=tool_name,
                arguments=arguments,
                actor=user_id,
                session_id=session_id,
                status="BLOCKED",
            )
            return PolicyDecision(
                allowed=False,
                risk_tier=RiskTier.HIGH,
                requires_approval=False,
                reason=f"Tool '{tool_name}' is not in the authorized tools allowlist.",
                sanitized_arguments=redact_secrets(arguments),
            )

        # 3. Risk classification
        risk = self.classify_risk(tool_name, arguments)
        needs_approval = (risk == RiskTier.HIGH)

        # 4. Low and Medium risk are auto-authorized
        if not needs_approval:
            return PolicyDecision(
                allowed=True,
                risk_tier=risk,
                requires_approval=False,
                reason="Auto-authorized by policy (Low/Medium risk).",
                sanitized_arguments=redact_secrets(arguments),
            )

        # 5. High risk requires verified approval token
        if not approval_id:
            req = approval_manager.create_request(
                tool_name=tool_name,
                arguments=arguments,
                session_id=session_id,
                risk_level=risk,
                user_id=user_id,
            )
            return PolicyDecision(
                allowed=False,
                risk_tier=risk,
                requires_approval=True,
                approval_id=req.request_id,
                reason=f"High-risk action requires human approval. Ticket: {req.request_id}",
                sanitized_arguments=redact_secrets(arguments),
            )

        # Verify and consume approval ticket with strict binding
        valid, reason = self.verify_approval(
            approval_id,
            arguments,
            tool_name=tool_name,
            session_id=session_id,
            user_id=user_id,
        )
        if not valid:
            return PolicyDecision(
                allowed=False,
                risk_tier=risk,
                requires_approval=True,
                approval_id=approval_id,
                reason=f"Authorization rejected: {reason}",
                sanitized_arguments=redact_secrets(arguments),
            )

        return PolicyDecision(
            allowed=True,
            risk_tier=risk,
            requires_approval=True,
            approval_id=approval_id,
            reason="Approved and verified by authorized human user.",
            sanitized_arguments=redact_secrets(arguments),
        )


# Global policy engine singleton
policy_engine = SecurityPolicyEngine()

