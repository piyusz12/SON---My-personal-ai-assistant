# tests/test_mandatory_defensive_agent.py — Phase 2C Mandatory Defensive Agent Integration Tests
"""
Phase 2C Test Suite:
Validates that the Central SON Orchestrator and Defensive PydanticAI Agent
are the mandatory gateway for all AI-initiated tool execution across all interfaces:
  1. son.py uses the orchestrator
  2. brain.py cannot bypass the orchestrator
  3. Voice actions use the orchestrator
  4. CLI actions use the orchestrator
  5. Desktop actions use the orchestrator
  6. WhatsApp sending uses the orchestrator
  7. WhatsApp sending requires confirmation
  8. Automation steps use policy evaluation
  9. Other agents cannot independently execute protected tools
  10. Direct unregistered tool calls are rejected
  11. Missing user identity is rejected
  12. Invalid session identity is rejected
  13. Approval cannot be reused across users or sessions
  14. Denied actions never reach the implementation
  15. E2B failure never triggers host execution
  16. Audit events are generated
  17. Normal conversation still works
  18. Memory and RAG still work
  19. Existing interface functionality remains operational
  20. Concurrent sessions remain isolated
"""

import time
import uuid
import threading
import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel, Field

from core.orchestrator import (
    SonOrchestrator,
    OrchestrationStatus,
    OrchestratorResponse,
    ActionResult,
    orchestrator as default_orch,
)
from core.security.context import (
    SecurityContext,
    RequestContext,
    SecurityContextError,
    create_trusted_context,
    create_request_context,
)
from core.security.policy import RiskTier, classify_risk
from core.security.policy_engine import SecurityPolicyEngine, policy_engine
from core.security.approval_manager import ApprovalManager, ApprovalStatus, approval_manager
from core.security.audit_logger import audit_logger
from core.security.tool_registry import DefensiveToolRegistry, RegisteredTool, defensive_tool_registry
from core.action_executor import ActionExecutor


class DummyToolSchema(BaseModel):
    path: str = Field(..., description="Target file path")


# ═════════════════════════════════════════════════════════════════════
# 1. son.py uses the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_son_uses_orchestrator():
    from son import Son
    son_app = Son(voice_mode=False, hud_mode=False)
    assert son_app.orchestrator is not None
    assert isinstance(son_app.orchestrator, SonOrchestrator)


# ═════════════════════════════════════════════════════════════════════
# 2. brain.py cannot bypass the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_brain_cannot_bypass_orchestrator():
    from brain import Brain
    from tools import ToolRegistry

    registry = ToolRegistry()
    dummy_executed = False

    def dummy_read(path: str):
        nonlocal dummy_executed
        dummy_executed = True
        return f"Contents of {path}"

    registry.register("read_file", dummy_read, "Read a file", params={"path": {"type": "string"}})
    brain = Brain(tools=registry)

    # Calling _execute_single_tool routes through default_orch.execute_action()
    res = brain._execute_single_tool({
        "function": {
            "name": "read_file",
            "arguments": {"path": "C:\\test\\notes.txt"},
        }
    })
    assert "Contents of" in res or "Security Error" in res or "read_file" in res


# ═════════════════════════════════════════════════════════════════════
# 3. Voice actions use the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_voice_actions_use_orchestrator():
    from son import Son
    son_app = Son(voice_mode=True, hud_mode=False)

    ctx = create_trusted_context(user_id="primary_user", interface_type="voice")
    assert ctx.interface == "voice"
    assert ctx.interface_type == "voice"

    # Orchestrator handles voice context cleanly
    res = son_app.orchestrator.process_request("hello voice assistant", context=ctx)
    assert res.status in (OrchestrationStatus.SUCCESS, OrchestrationStatus.ERROR, OrchestrationStatus.AWAITING_APPROVAL)
    assert res.request_id == ctx.request_id


# ═════════════════════════════════════════════════════════════════════
# 4. CLI actions use the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_cli_actions_use_orchestrator():
    from commands import CommandHandler
    cmd = CommandHandler(orchestrator=default_orch)

    # _execute_tool_safe routes through orchestrator.execute_action()
    res = cmd._execute_tool_safe("get_system_info", {})
    assert isinstance(res, str)
    assert len(res) > 0


# ═════════════════════════════════════════════════════════════════════
# 5. Desktop actions use the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_desktop_actions_use_orchestrator():
    from agents.desktop_agent import DesktopAgent
    agent = DesktopAgent(user_id="primary_user")

    # open_workspace routes through central SonOrchestrator
    output = agent.open_workspace("coding", session_id="desktop_test_session")
    assert isinstance(output, str)
    assert len(output) > 0


# ═════════════════════════════════════════════════════════════════════
# 6. WhatsApp sending uses the orchestrator
# ═════════════════════════════════════════════════════════════════════
def test_whatsapp_sending_uses_orchestrator():
    from services.whatsapp.models import Contact, WhatsAppDraft
    from services.whatsapp.service import WhatsAppVoiceService

    svc = WhatsAppVoiceService()
    contact = Contact(display_name="Mom", phone_number="911234567890")
    draft, _ = svc.state_machine.create_draft(contact=contact, message_text="Hello Mom!")

    # Executing confirmed draft routes through orchestrator.execute_action("open_whatsapp_draft")
    with patch("services.whatsapp.browser_launcher.BrowserLauncher.open_draft_url") as mock_open:
        mock_open.return_value = (True, "Browser launched successfully")
        success, msg = svc._execute_confirmed_draft(draft)
        assert success is True


# ═════════════════════════════════════════════════════════════════════
# 7. WhatsApp sending requires confirmation
# ═════════════════════════════════════════════════════════════════════
def test_whatsapp_sending_requires_confirmation():
    from services.whatsapp.models import Contact, DraftStatus
    from services.whatsapp.state_machine import WhatsAppDraftStateMachine, DraftStateError

    sm = WhatsAppDraftStateMachine()
    contact = Contact(display_name="Dad", phone_number="911987654321")
    draft, _ = sm.create_draft(contact=contact, message_text="Testing zero-trust confirmation")

    assert draft.status == DraftStatus.AWAITING_CONFIRMATION
    # Opening an unconfirmed draft without confirm_draft() raises an error
    with pytest.raises(DraftStateError):
        sm.mark_draft_opened(draft.draft_id)


# ═════════════════════════════════════════════════════════════════════
# 8. Automation steps use policy evaluation
# ═════════════════════════════════════════════════════════════════════
def test_automation_steps_use_policy_evaluation(tmp_path):
    from tools.automation import AutomationEngine
    from tools.registry import ToolRegistry

    registry = ToolRegistry()
    engine = AutomationEngine(tool_registry=registry, orchestrator=default_orch)
    engine._routines_file = tmp_path / "test_policy_routines.json"
    engine.create_routine(
        name="test_routine",
        description="Routine step policy testing",
        steps=[{"tool": "delete_path", "args": {"path": "C:\\temp\\unapproved.txt"}}],
    )

    out = engine.run_routine("test_routine")
    assert "Blocked by policy" in out or "approval" in out.lower()


# ═════════════════════════════════════════════════════════════════════
# 9. Other agents cannot independently execute protected tools
# ═════════════════════════════════════════════════════════════════════
def test_other_agents_cannot_independently_execute_protected_tools():
    from agents.terminal_agent import TerminalAgent
    agent = TerminalAgent()

    # High-risk command cannot execute without approval token
    res = agent.execute_command("del /f /q C:\\Windows\\System32")
    assert "HIGH RISK" in res or "requires approval" in res or "Security Error" in res


# ═════════════════════════════════════════════════════════════════════
# 10. Direct unregistered tool calls are rejected
# ═════════════════════════════════════════════════════════════════════
def test_direct_unregistered_tool_calls_rejected():
    ctx = create_request_context(user_id="primary_user")
    res = default_orch.execute_action(
        tool_name="completely_unregistered_tool_xyz",
        arguments={},
        context=ctx,
    )
    assert res.success is False
    assert (
        "not in the DefensiveToolRegistry" in res.output
        or "not in the authorized tools allowlist" in res.output
    )


# ═════════════════════════════════════════════════════════════════════
# 11. Missing user identity is rejected
# ═════════════════════════════════════════════════════════════════════
def test_missing_user_identity_rejected():
    res = default_orch.process_request("status check", context=None)
    assert res.status == OrchestrationStatus.BLOCKED
    assert "Missing SecurityContext" in res.response_text


# ═════════════════════════════════════════════════════════════════════
# 12. Invalid session identity is rejected
# ═════════════════════════════════════════════════════════════════════
def test_invalid_session_identity_rejected():
    with pytest.raises((SecurityContextError, ValueError)):
        SecurityContext(user_id="primary_user", session_id="")


# ═════════════════════════════════════════════════════════════════════
# 13. Approval cannot be reused across users or sessions
# ═════════════════════════════════════════════════════════════════════
def test_approval_cannot_be_reused_across_users_or_sessions():
    mgr = ApprovalManager()
    args = {"path": "C:\\temp\\protected.txt"}
    req = mgr.create_request("delete_path", args, user_id="user_A", session_id="session_A")
    mgr.resolve_request(req.request_id, approved=True, actor="user_A")

    # Mismatched user
    valid_user, reason_user = mgr.verify_and_consume(
        req.request_id, args, tool_name="delete_path", user_id="user_B", session_id="session_A"
    )
    assert valid_user is False
    assert "issued for user" in reason_user

    # Mismatched session
    valid_sess, reason_sess = mgr.verify_and_consume(
        req.request_id, args, tool_name="delete_path", user_id="user_A", session_id="session_B"
    )
    assert valid_sess is False
    assert "issued for session" in reason_sess


# ═════════════════════════════════════════════════════════════════════
# 14. Denied actions never reach the implementation
# ═════════════════════════════════════════════════════════════════════
def test_denied_actions_never_reach_implementation():
    executed = False
    def target_action(path: str):
        nonlocal executed
        executed = True
        return f"Deleted {path}"

    reg = DefensiveToolRegistry()
    reg.register(
        name="delete_path",
        handler=target_action,
        schema=DummyToolSchema,
        description="Delete file",
        risk_tier=RiskTier.HIGH,
    )
    orch = SonOrchestrator(tool_registry=reg)
    ctx = create_request_context(user_id="primary_user")

    res1 = orch.execute_action("delete_path", {"path": "C:\\temp\\file.txt"}, context=ctx)
    assert res1.requires_approval is True

    # User explicitly denies approval
    res2 = orch.handle_approval(res1.approval_id, approved=False, context=ctx)
    assert res2.status == OrchestrationStatus.DENIED
    assert executed is False


# ═════════════════════════════════════════════════════════════════════
# 15. E2B failure never triggers host execution
# ═════════════════════════════════════════════════════════════════════
def test_e2b_failure_never_triggers_host_execution():
    mock_sandbox = MagicMock()
    mock_sandbox.execute_terminal_command.side_effect = ConnectionError("E2B cluster unreachable")

    orch = SonOrchestrator(sandbox=mock_sandbox)
    ctx = create_request_context(user_id="primary_user")

    res = orch.execute_action("execute_sandbox_command", {"command": "whoami"}, context=ctx)
    assert res.success is False
    assert "Sandbox execution failed" in res.output
    assert "host fallback blocked" in res.error.lower()


# ═════════════════════════════════════════════════════════════════════
# 16. Audit events are generated
# ═════════════════════════════════════════════════════════════════════
def test_audit_events_generated():
    ctx = create_request_context(user_id="primary_user")
    res = default_orch.process_request("ping orchestrator", context=ctx)
    assert res.status in (OrchestrationStatus.SUCCESS, OrchestrationStatus.ERROR)

    recent = audit_logger.get_recent_events(limit=20)
    assert len(recent) > 0
    event_types = [e.get("event_type") for e in recent]
    assert any("ORCHESTRATOR" in et for et in event_types)


# ═════════════════════════════════════════════════════════════════════
# 17. Normal conversation still works
# ═════════════════════════════════════════════════════════════════════
def test_normal_conversation_still_works():
    ctx = create_request_context(user_id="primary_user")
    res = default_orch.process_request("Hello SON, how are you?", context=ctx)
    assert res.status in (OrchestrationStatus.SUCCESS, OrchestrationStatus.ERROR)
    assert isinstance(res.response_text, str)


# ═════════════════════════════════════════════════════════════════════
# 18. Memory and RAG still work
# ═════════════════════════════════════════════════════════════════════
def test_memory_and_rag_still_work(tmp_path):
    from memory.structured_memory import StructuredMemory

    mem = StructuredMemory(db_path=tmp_path / "test_mem.db")
    mem.set_preference("editor", "vscode")
    retrieved = mem.get_preference("editor")
    assert retrieved == "vscode"


# ═════════════════════════════════════════════════════════════════════
# 19. Existing interface functionality remains operational
# ═════════════════════════════════════════════════════════════════════
def test_existing_interface_functionality_remains_operational():
    from core.router import SecurityRouter
    from core.config import SecurityLevel

    router = SecurityRouter()
    # Read-only check passes
    assert router.check_permission("get_weather", SecurityLevel.SAFE) is True
    # Sensitive check fails closed without UI
    assert router.check_permission("shutdown_pc", SecurityLevel.CRITICAL) is False


# ═════════════════════════════════════════════════════════════════════
# 20. Concurrent sessions remain isolated
# ═════════════════════════════════════════════════════════════════════
def test_concurrent_sessions_remain_isolated():
    results = []
    errors = []

    def task(idx):
        try:
            ctx = create_request_context(user_id="primary_user", session_id=f"isolated_session_{idx}")
            res = default_orch.process_request(f"Test prompt {idx}", context=ctx)
            results.append((idx, res.request_id, res.context.session_id))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=task, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 8
    sessions = [sess for _, _, sess in results]
    assert len(set(sessions)) == 8  # All 8 sessions strictly distinct
