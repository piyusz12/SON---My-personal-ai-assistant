# core/security/approval_interface.py — Trusted Human Approval Boundary for SON V3
"""
Trusted Approval Boundary & Interface Protocol for SON V3:
Enforces:
  1. Safe display of proposed action and secret-redacted arguments.
  2. Clear identification of the requesting interface, session, and risk level.
  3. Explicit Approve and Deny decision primitives.
  4. Approver authorization verification (rejecting unauthorized actors).
  5. Prevention of stale approval dialogs from approving new or expired actions.
  6. Rejection of duplicate decisions.
  7. Audit logging of all approval interface interactions.
  8. Immunity to LLM boolean manipulation.
"""

import time
from typing import Any, Optional
from pydantic import BaseModel, Field

from core.security.identity import identity_manager
from core.security.context import SecurityContext, SecurityContextError
from core.security.approval_manager import ApprovalManager, approval_manager, ApprovalStatus, ApprovalRequest
from core.security.audit_logger import audit_logger, redact_secrets


class ApprovalDisplayModel(BaseModel):
    """Safe, human-readable presentation of an approval request."""
    approval_id: str
    tool_name: str
    arguments: dict[str, Any]
    requesting_interface: str
    requesting_user: str
    session_id: str
    risk_level: str
    reason: str
    created_at: float
    expires_at: float

    def format_terminal_text(self) -> str:
        """Render formatted display for terminal / CLI interfaces."""
        return (
            f"\n═══════════════════════════════════════════════════════════════\n"
            f" 🛡️  SON HUMAN AUTHORIZATION REQUIRED\n"
            f"═══════════════════════════════════════════════════════════════\n"
            f" Action:       {self.tool_name}\n"
            f" Risk Level:   {self.risk_level.upper()}\n"
            f" Request ID:   {self.approval_id}\n"
            f" Interface:    {self.requesting_interface} (User: {self.requesting_user})\n"
            f" Reason:       {self.reason}\n"
            f" Arguments:    {self.arguments}\n"
            f" Expiration:   {int(max(0, self.expires_at - time.time()))}s remaining\n"
            f"═══════════════════════════════════════════════════════════════\n"
        )


class TrustedApprovalInterface:
    """
    Secure boundary mediating between user-facing presentation layers
    (CLI, GUI, Voice) and the core ApprovalManager.
    """

    def __init__(self, manager: Optional[ApprovalManager] = None):
        self._manager = manager or approval_manager

    def format_request(
        self,
        request: ApprovalRequest,
        interface_type: str = "cli",
        reason: str = "Action exceeds automated safety policy tier.",
    ) -> ApprovalDisplayModel:
        """Transform an internal approval request into a safe presentation model."""
        return ApprovalDisplayModel(
            approval_id=request.request_id,
            tool_name=request.tool_name,
            arguments=redact_secrets(request.arguments),
            requesting_interface=interface_type,
            requesting_user=request.user_id,
            session_id=request.session_id,
            risk_level=request.risk_level.value,
            reason=reason,
            created_at=request.created_at,
            expires_at=request.expires_at,
        )

    def submit_decision(
        self,
        approval_id: str,
        approved: bool,
        approver_context: SecurityContext,
    ) -> tuple[bool, str]:
        """
        Validate approver authorization and submit decision to ApprovalManager.
        Enforces:
          - Approver context is authenticated and active.
          - Approver identity has permission to grant approvals.
          - Expired, duplicate, or stale requests are rejected.
        """
        if approver_context is None or not getattr(approver_context, "is_authenticated", False):
            audit_logger.log_event(
                event_type="UNAUTHENTICATED_APPROVAL_ATTEMPT_BLOCKED",
                approval_id=approval_id,
                status="BLOCKED",
                details={"reason": "Approver context is not authenticated."},
            )
            return False, "Security Error: Approver must be authenticated."

        approver_uid = approver_context.user_id

        # Verify approver authority in IdentityManager
        if not identity_manager.can_user_approve(approver_uid):
            audit_logger.log_event(
                event_type="UNAUTHORIZED_APPROVER_BLOCKED",
                approval_id=approval_id,
                actor=approver_uid,
                session_id=approver_context.session_id,
                status="BLOCKED",
                details={"reason": f"User '{approver_uid}' lacks authorization to approve sensitive actions."},
            )
            return False, f"Security violation: User '{approver_uid}' is not authorized to grant approvals."

        # Fetch and verify request status
        req = self._manager.get_request(approval_id)
        if not req:
            audit_logger.log_event(
                event_type="APPROVAL_UNKNOWN_ID",
                approval_id=approval_id,
                actor=approver_uid,
                status="REJECTED",
                details={"reason": "Approval request ID not found."},
            )
            return False, f"Approval request '{approval_id}' not found."

        # Check stale / expired
        if req.status == ApprovalStatus.EXPIRED or req.is_expired():
            audit_logger.log_event(
                event_type="STALE_APPROVAL_DIALOG_REJECTED",
                approval_id=approval_id,
                actor=approver_uid,
                status="BLOCKED",
                details={"reason": "Attempted decision on expired or stale dialog."},
            )
            return False, f"Approval request '{approval_id}' has expired."

        # Check duplicate resolution
        if req.status != ApprovalStatus.PENDING:
            audit_logger.log_event(
                event_type="DUPLICATE_DECISION_REJECTED",
                approval_id=approval_id,
                actor=approver_uid,
                status="BLOCKED",
                details={"current_status": req.status.value},
            )
            return False, f"Approval request '{approval_id}' is already {req.status.value}."

        # Forward to ApprovalManager
        success, message = self._manager.resolve_request(
            request_id=approval_id,
            approved=approved,
            actor=approver_uid,
        )

        return success, message


# Singleton instance
trusted_approval_interface = TrustedApprovalInterface()

