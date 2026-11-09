# tests/test_identity_session_approval.py — Comprehensive Test Suite for Phase 2D
"""
Defensive Verification Test Suite for SON V3 Phase 2D:
Validates all 22 required areas:
  1. Unique session generation
  2. Correct user-session association
  3. Cross-user session rejection
  4. Cross-session request rejection
  5. Expired session rejection
  6. Revoked session rejection
  7. Missing identity rejection
  8. Model-generated identity manipulation
  9. Approval bound to exact arguments
  10. Approval bound to exact tool
  11. Approval bound to exact user
  12. Approval bound to exact session
  13. Expired approval rejection
  14. Cancelled approval rejection
  15. Replay prevention
  16. Duplicate decision rejection
  17. Atomic approval consumption under concurrency
  18. Unauthorized approver rejection
  19. Stale approval request rejection
  20. Application restart behavior
  21. Audit event creation
  22. Concurrent user isolation
"""

import time
import uuid
import pytest
import concurrent.futures
from pathlib import Path

from core.security.identity import identity_manager, UserRole, UserProfile
from core.security.session_manager import session_manager, SessionStatus
from core.security.approval_manager import ApprovalManager, ApprovalStatus
from core.security.approval_interface import TrustedApprovalInterface
from core.security.context import (
    SecurityContext,
    RequestContext,
    SecurityContextError,
    create_trusted_context,
    create_request_context,
)
from core.security.audit_logger import audit_logger
from core.orchestrator import SonOrchestrator, OrchestrationStatus
from core.action_executor import ActionExecutor
from core.config import SecurityLevel


# 1. Unique session generation
def test_unique_session_generation():
    sessions = [session_manager.create_session(user_id="primary_user") for _ in range(50)]
    session_ids = [s.session_id for s in sessions]
    assert len(set(session_ids)) == 50
    for sid in session_ids:
        assert sid.startswith("sess_")
        assert len(sid) >= 30


# 2. Correct user-session association
def test_correct_user_session_association():
    sess = session_manager.create_session(user_id="father", interface_type="voice")
    assert sess.user_id == "father"
    assert sess.canonical_user_id == "usr_primary"
    assert sess.interface_type == "voice"
    assert sess.status == SessionStatus.ACTIVE
    assert sess.is_expired() is False

    valid, msg, retrieved = session_manager.validate_session(sess.session_id, user_id="father")
    assert valid is True
    assert retrieved is not None
    assert retrieved.session_id == sess.session_id


# 3. Cross-user session rejection
def test_cross_user_session_rejection():
    sess = session_manager.create_session(user_id="primary_user")
    valid, reason, _ = session_manager.validate_session(sess.session_id, user_id="usr_automation")
    assert valid is False
    assert "belongs to user" in reason or "Security violation" in reason


# 4. Cross-session request rejection
def test_cross_session_request_rejection():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args, session_id="session_A", user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    valid, reason = mgr.verify_and_consume(
        req.request_id,
        args,
        tool_name="delete_path",
        session_id="session_B",
        user_id="primary_user",
    )
    assert valid is False
    assert "Approval token was issued for session 'session_A', not 'session_B'" in reason


# 5. Expired session rejection
def test_expired_session_rejection():
    sess = session_manager.create_session(user_id="primary_user", ttl_seconds=0.01)
    time.sleep(0.03)

    valid, reason, _ = session_manager.validate_session(sess.session_id, user_id="primary_user")
    assert valid is False
    assert "expired" in reason.lower()


# 6. Revoked session rejection
def test_revoked_session_rejection():
    sess = session_manager.create_session(user_id="primary_user")
    revoked = session_manager.revoke_session(sess.session_id, actor="admin")
    assert revoked is True

    valid, reason, _ = session_manager.validate_session(sess.session_id, user_id="primary_user")
    assert valid is False
    assert "revoked" in reason.lower()


# 7. Missing identity rejection
def test_missing_identity_rejection():
    with pytest.raises(SecurityContextError):
        create_trusted_context(user_id="")

    with pytest.raises(SecurityContextError):
        create_trusted_context(user_id="   ")


# 8. Model-generated identity manipulation
def test_model_generated_identity_manipulation():
    # Simulate an LLM attempting to fabricate an identity inside arguments or prompt
    orch = SonOrchestrator()
    untrusted_llm_json = {
        "text": "run_command",
        "user_id": "root",
        "is_authenticated": True,
        "session_id": "forged_admin_session",
    }
    # Orchestrator strictly ignores model output fields and requires trusted application context
    valid_context = create_trusted_context(user_id="primary_user")
    res = orch.process_request(str(untrusted_llm_json), context=valid_context)
    # Execution must remain bound to the trusted context, not forged_admin_session
    assert res.context.user_id == "primary_user"
    assert res.context.session_id == valid_context.session_id


# 9. Approval bound to exact arguments
def test_approval_bound_to_exact_arguments():
    mgr = ApprovalManager()
    approved_args = {"path": "C:\\safe\\file.txt"}
    tampered_args = {"path": "C:\\Windows\\System32\\cmd.exe"}
    req = mgr.create_request("delete_path", approved_args, user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    valid, reason = mgr.verify_and_consume(req.request_id, tampered_args)
    assert valid is False
    assert "Arguments have been modified" in reason


# 10. Approval bound to exact tool
def test_approval_bound_to_exact_tool():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args, user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    valid, reason = mgr.verify_and_consume(req.request_id, args, tool_name="write_file")
    assert valid is False
    assert "issued for tool 'delete_path', not 'write_file'" in reason


# 11. Approval bound to exact user
def test_approval_bound_to_exact_user():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args, user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    valid, reason = mgr.verify_and_consume(req.request_id, args, user_id="automation_scheduler")
    assert valid is False
    assert "issued for user 'primary_user', not 'automation_scheduler'" in reason


# 12. Approval bound to exact session
def test_approval_bound_to_exact_session():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args, session_id="sess_1", user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    valid, reason = mgr.verify_and_consume(req.request_id, args, session_id="sess_2")
    assert valid is False
    assert "issued for session 'sess_1', not 'sess_2'" in reason


# 13. Expired approval rejection
def test_expired_approval_rejection():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args, ttl_seconds=0.01)
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    time.sleep(0.03)
    valid, reason = mgr.verify_and_consume(req.request_id, args)
    assert valid is False
    assert "expired" in reason.lower()


# 14. Cancelled approval rejection
def test_cancelled_approval_rejection():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args)
    mgr.cancel_request(req.request_id, actor="primary_user")

    valid, reason = mgr.verify_and_consume(req.request_id, args)
    assert valid is False
    assert "cancelled" in reason.lower()


# 15. Replay prevention
def test_replay_prevention():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\file.txt"}
    req = mgr.create_request("delete_path", args)
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    v1, _ = mgr.verify_and_consume(req.request_id, args)
    assert v1 is True

    v2, reason2 = mgr.verify_and_consume(req.request_id, args)
    assert v2 is False
    assert "Replay attack detected" in reason2


# 16. Duplicate decision rejection
def test_duplicate_decision_rejection():
    mgr = ApprovalManager()
    req = mgr.create_request("delete_path", {"path": "C:\\temp\\file.txt"})

    success1, msg1 = mgr.resolve_request(req.request_id, approved=True, actor="primary_user")
    assert success1 is True

    # Second decision attempt on same request must be rejected
    success2, msg2 = mgr.resolve_request(req.request_id, approved=False, actor="primary_user")
    assert success2 is False
    assert "is already APPROVED" in msg2


# 17. Atomic approval consumption under concurrency
def test_atomic_approval_consumption_under_concurrency():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\concurrent.txt"}
    req = mgr.create_request("delete_path", args)
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")

    success_count = 0
    failure_count = 0

    def consume():
        valid, _ = mgr.verify_and_consume(req.request_id, args)
        return valid

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(consume) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)

    # Exactly one thread succeeds; all other 19 fail
    assert success_count == 1
    assert failure_count == 19


# 18. Unauthorized approver rejection
def test_unauthorized_approver_rejection():
    # User with can_approve=False
    identity_manager.register_user(
        user_id="operator_bob",
        display_name="Operator Bob",
        role=UserRole.OPERATOR,
        can_approve=False,
    )
    ui_interface = TrustedApprovalInterface()
    mgr = ApprovalManager()
    req = mgr.create_request("delete_path", {"path": "C:\\data.txt"})
    ui_interface._manager = mgr

    unauthorized_ctx = create_trusted_context(user_id="operator_bob")
    success, reason = ui_interface.submit_decision(
        approval_id=req.request_id,
        approved=True,
        approver_context=unauthorized_ctx,
    )
    assert success is False
    assert "not authorized to grant approvals" in reason


# 19. Stale approval request rejection
def test_stale_approval_request_rejection():
    ui_interface = TrustedApprovalInterface()
    mgr = ApprovalManager()
    req = mgr.create_request("delete_path", {"path": "C:\\data.txt"}, ttl_seconds=0.01)
    ui_interface._manager = mgr

    time.sleep(0.03)
    authorized_ctx = create_trusted_context(user_id="primary_user")
    success, reason = ui_interface.submit_decision(
        approval_id=req.request_id,
        approved=True,
        approver_context=authorized_ctx,
    )
    assert success is False
    assert "expired" in reason.lower()


# 20. Application restart behavior
def test_application_restart_behavior():
    mgr = ApprovalManager()
    # Create several pending approvals
    req1 = mgr.create_request("delete_path", {"path": "1.txt"})
    req2 = mgr.create_request("delete_path", {"path": "2.txt"})

    # Simulate restart: clean reset
    invalidated = mgr.reset_on_startup()
    assert invalidated >= 2

    # Verification must fail closed on old tokens
    v1, r1 = mgr.verify_and_consume(req1.request_id, {"path": "1.txt"})
    assert v1 is False
    assert "not found" in r1.lower()


# 21. Audit event creation
def test_audit_event_creation():
    # Trigger lifecycle actions and verify events in audit log
    sess = session_manager.create_session(user_id="primary_user")
    session_manager.validate_session(sess.session_id, user_id="primary_user")

    mgr = ApprovalManager()
    req = mgr.create_request("delete_path", {"path": "C:\\audit_test.txt"}, user_id="primary_user")
    mgr.resolve_request(req.request_id, approved=True, actor="primary_user")
    mgr.verify_and_consume(req.request_id, {"path": "C:\\audit_test.txt"})

    events = audit_logger.get_recent_events(limit=50)
    event_types = {e["event_type"] for e in events}

    assert "SESSION_CREATED" in event_types
    assert "SESSION_VALIDATED" in event_types
    assert "APPROVAL_REQUEST_CREATED" in event_types
    assert "APPROVAL_APPROVED" in event_types or "APPROVAL_GRANTED" in event_types
    assert "PROTECTED_ACTION_EXECUTED" in event_types


# 22. Concurrent user isolation
def test_concurrent_user_isolation():
    orch = SonOrchestrator()
    users = ["primary_user", "usr_automation"]

    def run_user_request(uid: str):
        ctx = create_trusted_context(user_id=uid)
        res = orch.process_request("hello", context=ctx)
        return uid, ctx.session_id, res.status

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_user_request, users[i % len(users)]) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10
    # Confirm every session was uniquely allocated and isolated
    sids = [r[1] for r in results]
    assert len(set(sids)) == 10

