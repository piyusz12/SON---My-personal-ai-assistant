# core/security/approval_manager.py — Human-in-the-Loop Authorization Engine
"""
Server-side approval state machine providing:
  - Risk-tiered authorization (LOW, MEDIUM, HIGH)
  - Single-use, time-expiring approval requests (UUID4)
  - Exact cryptographic argument hash binding (SHA-256)
  - Replay protection (tokens cannot be re-used)
  - Expiration enforcement (default 120 seconds TTL)
  - Tamper-proofing against parameter modification
  - Structured audit trail
"""

import time
import uuid
import threading
from enum import Enum
from typing import Any, Callable

from core.security.policy import RiskTier, classify_risk
from core.security.audit_logger import audit_logger, canonical_args_hash, redact_secrets


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class ApprovalRequest:
    """Represents a single, immutable authorization request."""

    def __init__(
        self,
        request_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: RiskTier,
        ttl_seconds: float = 120.0,
    ):
        self.request_id = request_id
        self.session_id = session_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.args_hash = canonical_args_hash(arguments)
        self.risk_level = risk_level
        self.status = ApprovalStatus.PENDING
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.resolved_at: float | None = None
        self.resolved_by: str | None = None
        self.execution_result: Any = None

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "arguments": redact_secrets(self.arguments),
            "args_hash": self.args_hash,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired(),
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }


class ApprovalManager:
    """
    Manages the lifecycle of approval requests.
    Guarantees that dangerous operations cannot run without explicit authorization,
    arguments cannot be tampered with between approval and execution,
    and approvals cannot be replayed.
    Thread-safe and bounds memory consumption through automatic request pruning.
    """

    def __init__(self, ui_prompt_callback: Callable[[ApprovalRequest], bool] | None = None):
        self._requests: dict[str, ApprovalRequest] = {}
        self._ui_callback = ui_prompt_callback
        self._lock = threading.RLock()

    def set_ui_callback(self, callback: Callable[[ApprovalRequest], bool]):
        with self._lock:
            self._ui_callback = callback

    def prune_stale_requests(self, max_age_seconds: float = 3600.0, max_entries: int = 500) -> int:
        """
        Prune consumed or expired approval requests to prevent unbounded memory growth.
        Leaves unexpired pending requests intact.
        Returns the count of purged requests.
        """
        with self._lock:
            if len(self._requests) < max_entries:
                return 0

            now = time.time()
            to_delete = []
            for req_id, req in self._requests.items():
                is_stale = (
                    req.status in (ApprovalStatus.CONSUMED, ApprovalStatus.DENIED, ApprovalStatus.EXPIRED)
                    or (req.status == ApprovalStatus.PENDING and req.is_expired())
                )
                if is_stale and (now - req.created_at) > max_age_seconds:
                    to_delete.append(req_id)

            for req_id in to_delete:
                del self._requests[req_id]

            return len(to_delete)

    def create_request(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str = "default_session",
        risk_level: RiskTier | None = None,
        ttl_seconds: float = 120.0,
    ) -> ApprovalRequest:
        """Create and record a new server-side approval request."""
        risk = risk_level or classify_risk(tool_name, arguments)
        req_id = str(uuid.uuid4())

        req = ApprovalRequest(
            request_id=req_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk,
            ttl_seconds=ttl_seconds,
        )

        with self._lock:
            # Self-prune if collection exceeds high-water mark
            if len(self._requests) >= 500:
                self.prune_stale_requests(max_age_seconds=600.0, max_entries=500)
            self._requests[req_id] = req

        audit_logger.log_event(
            event_type="APPROVAL_REQUEST_CREATED",
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk.value,
            session_id=session_id,
            approval_id=req_id,
            status="PENDING",
            details={"ttl_seconds": ttl_seconds},
        )
        return req

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Retrieve an existing approval request, checking expiration."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                return None

            if req.status == ApprovalStatus.PENDING and req.is_expired():
                req.status = ApprovalStatus.EXPIRED
                audit_logger.log_event(
                    event_type="APPROVAL_EXPIRED",
                    tool_name=req.tool_name,
                    arguments=req.arguments,
                    risk_level=req.risk_level.value,
                    session_id=req.session_id,
                    approval_id=req.request_id,
                    status="EXPIRED",
                )
            return req

    def resolve_request(
        self,
        request_id: str,
        approved: bool,
        actor: str = "user",
    ) -> tuple[bool, str]:
        """
        Approve or deny an existing pending request.
        """
        with self._lock:
            req = self.get_request(request_id)
            if not req:
                audit_logger.log_event(
                    event_type="APPROVAL_UNKNOWN_ID",
                    approval_id=request_id,
                    status="REJECTED",
                    actor=actor,
                    details={"reason": "Request ID not found"},
                )
                return False, f"Approval request '{request_id}' not found."

            if req.status == ApprovalStatus.EXPIRED or req.is_expired():
                req.status = ApprovalStatus.EXPIRED
                return False, f"Approval request '{request_id}' has expired."

            if req.status == ApprovalStatus.CONSUMED:
                return False, f"Approval request '{request_id}' has already been consumed (replay blocked)."

            if req.status != ApprovalStatus.PENDING:
                return False, f"Approval request '{request_id}' is already {req.status.value}."

            req.resolved_at = time.time()
            req.resolved_by = actor
            if approved:
                req.status = ApprovalStatus.APPROVED
                audit_logger.log_event(
                    event_type="APPROVAL_GRANTED",
                    tool_name=req.tool_name,
                    arguments=req.arguments,
                    risk_level=req.risk_level.value,
                    session_id=req.session_id,
                    approval_id=req.request_id,
                    status="APPROVED",
                    actor=actor,
                )
                return True, "Approved."
            else:
                req.status = ApprovalStatus.DENIED
                audit_logger.log_event(
                    event_type="APPROVAL_DENIED",
                    tool_name=req.tool_name,
                    arguments=req.arguments,
                    risk_level=req.risk_level.value,
                    session_id=req.session_id,
                    approval_id=req.request_id,
                    status="DENIED",
                    actor=actor,
                )
                return False, "Denied by user."

    def verify_and_consume(
        self,
        request_id: str,
        arguments_to_execute: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Verify that:
        1. Request exists and is in APPROVED status.
        2. Request has not expired.
        3. Request has not already been consumed (replay protection).
        4. Arguments match the exact SHA-256 hash when approved (tamper protection).
        
        If verified, atomically transitions to CONSUMED.
        """
        with self._lock:
            req = self.get_request(request_id)
            if not req:
                audit_logger.log_event(
                    event_type="SECURITY_VIOLATION",
                    approval_id=request_id,
                    status="BLOCKED",
                    details={"reason": "Attempt to consume nonexistent approval token"},
                )
                return False, "Invalid approval token: request not found."

            if req.status == ApprovalStatus.CONSUMED:
                audit_logger.log_event(
                    event_type="SECURITY_VIOLATION_REPLAY",
                    tool_name=req.tool_name,
                    approval_id=request_id,
                    status="BLOCKED",
                    details={"reason": "Replay attack detected: approval token already consumed"},
                )
                return False, "Security violation: Replay attack detected. Approval token has already been used."

            if req.status == ApprovalStatus.EXPIRED or req.is_expired():
                req.status = ApprovalStatus.EXPIRED
                audit_logger.log_event(
                    event_type="APPROVAL_EXPIRED",
                    tool_name=req.tool_name,
                    approval_id=request_id,
                    status="EXPIRED",
                )
                return False, "Approval expired. Operation cancelled."

            if req.status != ApprovalStatus.APPROVED:
                audit_logger.log_event(
                    event_type="SECURITY_VIOLATION_UNAPPROVED",
                    tool_name=req.tool_name,
                    approval_id=request_id,
                    status="BLOCKED",
                    details={"status": req.status.value},
                )
                return False, f"Operation not approved (current status: {req.status.value})."

            # Tamper check: recompute argument hash
            exec_hash = canonical_args_hash(arguments_to_execute)
            if exec_hash != req.args_hash:
                audit_logger.log_event(
                    event_type="SECURITY_VIOLATION_TAMPERING",
                    tool_name=req.tool_name,
                    approval_id=request_id,
                    status="BLOCKED",
                    details={
                        "reason": "Argument tampering detected between approval and execution",
                        "approved_hash": req.args_hash,
                        "execution_hash": exec_hash,
                    },
                )
                return False, "Security violation: Arguments have been modified after approval was granted."

            # Mark as consumed immediately (atomic single-use)
            req.status = ApprovalStatus.CONSUMED
            audit_logger.log_event(
                event_type="APPROVAL_CONSUMED",
                tool_name=req.tool_name,
                arguments=arguments_to_execute,
                risk_level=req.risk_level.value,
                session_id=req.session_id,
                approval_id=request_id,
                status="CONSUMED",
            )
            return True, "Verified and consumed."

    def authorize_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str = "default_session",
    ) -> tuple[bool, str, ApprovalRequest | None]:
        """
        High-level gatekeeper for an action.
        - LOW risk: Auto-approved.
        - MEDIUM risk: Auto-approved unless destructive flags detected.
        - HIGH risk: Requires explicit interactive approval via UI or prompt.
        """
        risk = classify_risk(tool_name, arguments)
        if risk != RiskTier.HIGH:
            # Low or Medium risk is permitted by policy
            audit_logger.log_event(
                event_type="TOOL_AUTO_AUTHORIZED",
                tool_name=tool_name,
                arguments=arguments,
                risk_level=risk.value,
                session_id=session_id,
                status="AUTHORIZED",
            )
            return True, "Auto-authorized.", None

        # HIGH risk requires explicit human-in-the-loop approval
        req = self.create_request(tool_name, arguments, session_id=session_id, risk_level=risk)

        if self._ui_callback:
            approved = self._ui_callback(req)
            success, msg = self.resolve_request(req.request_id, approved=approved, actor="user")
            if success:
                valid, reason = self.verify_and_consume(req.request_id, arguments)
                return valid, reason, req
            return False, msg, req

        # Fail-closed: No UI callback available to confirm HIGH risk
        audit_logger.log_event(
            event_type="TOOL_BLOCKED_NO_UI",
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk.value,
            session_id=session_id,
            approval_id=req.request_id,
            status="BLOCKED_FAIL_CLOSED",
            details={"reason": "High-risk operation requires human approval, but no interactive UI is registered."},
        )
        return False, f"High-risk action '{tool_name}' blocked by fail-closed policy (requires explicit human approval).", req


# Global approval manager singleton
approval_manager = ApprovalManager()

