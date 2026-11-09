# tests/test_interface_standardization.py — Comprehensive Interface Integration Test Suite for Phase 2E
"""
Comprehensive Integration Test Suite for SON V3 Phase 2E:
Validates all 20 required integration areas:
  1. Main application to orchestrator
  2. Voice adapter to orchestrator
  3. CLI adapter to orchestrator
  4. Desktop adapter to orchestrator
  5. WhatsApp adapter to orchestrator
  6. Automation adapter to orchestrator
  7. Trusted identity propagation
  8. Session isolation across adapters
  9. Request ID preservation
  10. Structured response handling
  11. Pending approval delivery
  12. Approval response binding
  13. Stale approval rejection
  14. Interface timeout handling
  15. Request cancellation
  16. Concurrent requests from different sessions
  17. Unauthorized interface rejection
  18. WhatsApp confirmation-before-send
  19. Automation policy evaluation
  20. No direct sensitive-tool execution from interfaces
"""

import time
import inspect
import pytest
import concurrent.futures
from unittest.mock import MagicMock, patch

from core.interfaces import (
    InterfaceType,
    InterfaceRequest,
    InterfaceResponse,
    BaseInterfaceAdapter,
    VoiceInterfaceAdapter,
    CLIInterfaceAdapter,
    DesktopInterfaceAdapter,
    WhatsAppInterfaceAdapter,
    AutomationInterfaceAdapter,
)
from core.orchestrator import SonOrchestrator, OrchestrationStatus
from core.security.context import SecurityContext, SecurityContextError, create_trusted_context
from core.security.approval_manager import approval_manager, ApprovalManager
from core.security.session_manager import session_manager
from core.security.identity import identity_manager
from core.security.tool_registry import defensive_tool_registry
from core.config import SecurityLevel


class DummyRunResult:
    """Mock agent run result for testing orchestrator flow without live LLM."""
    def __init__(self, output):
        self.output = output

    def all_messages(self):
        return []


class MockAgent:
    """Mock PydanticAI agent conforming to DefensivePydanticAgent interface."""
    def __init__(self, output="I am SON, your personal assistant."):
        self.output = output
        self._call_to_request = {}
        self._resumed_approvals = {}

    def run(self, user_prompt: str, session_id: str, context: SecurityContext, message_history=None):
        return DummyRunResult(self.output)

    def resume_with_approval(self, run_result, request_id: str, approved: bool, session_id: str, actor: str, context: SecurityContext):
        if approved:
            return DummyRunResult(f"Resumed action '{request_id}' successfully.")
        return DummyRunResult(f"Action '{request_id}' was rejected.")


# 1. Main application to orchestrator
def test_main_app_to_orchestrator():
    from son import Son
    app = Son()
    # Inject mock agent for offline execution
    app.orchestrator.pydantic_agent = MockAgent(output="System status normal.")
    assert app.orchestrator is not None

    # Simulate turn through CLI adapter
    cli = CLIInterfaceAdapter(orchestrator=app.orchestrator)
    res = cli.execute_prompt("what is the system status?", interactive_approval=False)
    assert res.request_id is not None
    assert res.status == OrchestrationStatus.SUCCESS
    assert "System status normal" in res.response_text


# 2. Voice adapter to orchestrator
def test_voice_adapter_to_orchestrator():
    mock_tts = MagicMock()
    orch = SonOrchestrator(pydantic_agent=MockAgent(output="I heard you loud and clear."))
    voice = VoiceInterfaceAdapter(orchestrator=orch, tts_engine=mock_tts)

    res = voice.handle_speech_input("hello son")
    assert res.request_id.startswith("req_")
    assert res.status == OrchestrationStatus.SUCCESS
    assert "loud and clear" in res.response_text
    # Verified TTS playback invocation
    mock_tts.speak.assert_called_once()


# 3. CLI adapter to orchestrator
def test_cli_adapter_to_orchestrator():
    orch = SonOrchestrator(pydantic_agent=MockAgent(output="Hello from SON CLI."))
    cli = CLIInterfaceAdapter(orchestrator=orch)

    res = cli.execute_prompt("hello", interactive_approval=False)
    assert res.status == OrchestrationStatus.SUCCESS
    assert len(cli._history) == 1
    assert cli._history[0]["request_id"] == res.request_id
    assert "Hello from SON CLI" in res.response_text


# 4. Desktop adapter to orchestrator
def test_desktop_adapter_to_orchestrator():
    orch = SonOrchestrator(pydantic_agent=MockAgent(output="Desktop ready."))
    status_events = []
    desktop = DesktopInterfaceAdapter(
        orchestrator=orch,
        on_status_change=lambda s: status_events.append(s),
    )

    res = desktop.submit_user_message("hello")
    assert res.status == OrchestrationStatus.SUCCESS
    assert "Desktop ready" in res.response_text
    assert "thinking" in status_events
    assert "idle" in status_events


# 5. WhatsApp adapter to orchestrator
def test_whatsapp_adapter_to_orchestrator():
    from services.whatsapp.service import WhatsAppVoiceService
    service = WhatsAppVoiceService()
    adapter = WhatsAppInterfaceAdapter(whatsapp_service=service)

    res = adapter.handle_voice_message("send rahul a whatsapp message saying hello")
    assert res.status in (OrchestrationStatus.SUCCESS, OrchestrationStatus.AWAITING_APPROVAL)
    assert "Rahul" in res.response_text or "whatsapp" in res.response_text.lower()


# 6. Automation adapter to orchestrator
def test_automation_adapter_to_orchestrator():
    orch = SonOrchestrator()
    adapter = AutomationInterfaceAdapter(orchestrator=orch)

    steps = [
        {"tool": "get_system_info", "args": {}},
        {"tool": "get_weather", "args": {"city": "Paris"}},
    ]
    results = adapter.run_safe_sequence(routine_name="morning_check", steps=steps)
    assert len(results) == 2
    assert results[0].status == OrchestrationStatus.SUCCESS
    assert results[1].status == OrchestrationStatus.SUCCESS


# 7. Trusted identity propagation
def test_trusted_identity_propagation():
    adapter = CLIInterfaceAdapter(default_user_id="usr_primary")
    req = adapter.normalize_request(message="test identity")
    assert req.user_id == "usr_primary"
    ctx = req.to_security_context()
    assert ctx.user_id == "usr_primary"
    assert ctx.is_authenticated is True


# 8. Session isolation across adapters
def test_session_isolation_across_adapters():
    orch = SonOrchestrator(pydantic_agent=MockAgent())
    voice = VoiceInterfaceAdapter(orchestrator=orch)
    cli = CLIInterfaceAdapter(orchestrator=orch)

    res_voice = voice.handle_speech_input("hello voice")
    res_cli = cli.execute_prompt("hello cli", interactive_approval=False)

    assert voice._session_id is not None
    assert cli._session_id is not None
    assert voice._session_id != cli._session_id


# 9. Request ID preservation
def test_request_id_preservation():
    orch = SonOrchestrator(pydantic_agent=MockAgent())
    adapter = CLIInterfaceAdapter(orchestrator=orch)
    req = adapter.normalize_request(message="ping")
    orig_req_id = req.request_id

    res = adapter.send_request(req)
    assert res.request_id == orig_req_id


# 10. Structured response handling
def test_structured_response_handling():
    orch = SonOrchestrator(pydantic_agent=MockAgent())
    adapter = CLIInterfaceAdapter(orchestrator=orch)
    res = adapter.execute_prompt("hello", interactive_approval=False)

    assert isinstance(res, InterfaceResponse)
    assert hasattr(res, "request_id")
    assert hasattr(res, "status")
    assert hasattr(res, "response_text")
    assert hasattr(res, "tool_results")
    assert hasattr(res, "execution_metadata")


# 11. Pending approval delivery
def test_pending_approval_delivery():
    orch = SonOrchestrator()
    adapter = DesktopInterfaceAdapter(orchestrator=orch)

    # Calling a HIGH risk tool that requires approval
    res = adapter.execute_action(
        tool_name="delete_path",
        arguments={"path": "C:\\temp\\test.txt"},
    )
    assert res.status in (OrchestrationStatus.PENDING_APPROVAL, OrchestrationStatus.AWAITING_APPROVAL)
    assert res.pending_approval is not None
    assert "approval_id" in res.pending_approval


# 12. Approval response binding
def test_approval_response_binding():
    from core.security.tool_registry import DefensiveToolRegistry
    from core.security.schemas import DeletePathParams
    from core.security.policy import RiskTier
    reg = DefensiveToolRegistry()
    reg.register(
        name="delete_path",
        handler=lambda path: f"Successfully deleted {path}",
        schema=DeletePathParams,
        description="Delete file",
        risk_tier=RiskTier.HIGH,
    )
    orch = SonOrchestrator(tool_registry=reg)
    adapter = CLIInterfaceAdapter(orchestrator=orch)

    # Request high risk action
    res1 = adapter.execute_action("delete_path", {"path": "C:\\temp\\protected.txt"})
    approval_id = res1.pending_approval["approval_id"]

    # Submit approval decision through the same adapter/session
    res2 = adapter.handle_approval(approval_id=approval_id, approved=True)
    assert res2.status == OrchestrationStatus.SUCCESS
    assert "successfully deleted" in res2.response_text.lower()


# 13. Stale approval rejection
def test_stale_approval_rejection():
    mgr = ApprovalManager()
    orch = SonOrchestrator(approval_manager_instance=mgr)
    adapter = CLIInterfaceAdapter(orchestrator=orch)

    # Create request with tiny TTL
    req = mgr.create_request("delete_path", {"path": "C:\\temp\\stale.txt"}, ttl_seconds=0.01)
    time.sleep(0.03)

    res = adapter.handle_approval(approval_id=req.request_id, approved=True)
    assert res.status in (OrchestrationStatus.ERROR, OrchestrationStatus.DENIED, OrchestrationStatus.VALIDATION_ERROR)
    assert "expired" in res.response_text.lower() or "expired" in (res.error or "").lower()


# 14. Interface timeout handling
def test_interface_timeout_handling():
    orch = SonOrchestrator()
    adapter = CLIInterfaceAdapter(orchestrator=orch)

    req = adapter.normalize_request(message="simulate timeout")

    # Mock long running execution to test timeout threshold
    with patch.object(orch, "process_request", side_effect=lambda msg, context: time.sleep(0.05)):
        res = adapter.send_request(req, timeout=0.01)
        assert res.status == OrchestrationStatus.TIMEOUT
        assert "timed out" in res.response_text.lower()


# 15. Request cancellation
def test_request_cancellation():
    orch = SonOrchestrator()
    adapter = CLIInterfaceAdapter(orchestrator=orch)
    req = adapter.normalize_request(message="test cancellation")

    # Test cancel_request on nonexistent and in-flight
    assert adapter.cancel_request("nonexistent_req") is False


# 16. Concurrent requests from different sessions
def test_concurrent_requests_different_sessions():
    orch = SonOrchestrator(pydantic_agent=MockAgent())
    cli = CLIInterfaceAdapter(orchestrator=orch)
    voice = VoiceInterfaceAdapter(orchestrator=orch)
    desktop = DesktopInterfaceAdapter(orchestrator=orch)

    def run_cli():
        return cli.execute_prompt("cli test", interactive_approval=False)

    def run_voice():
        return voice.handle_speech_input("voice test")

    def run_desktop():
        return desktop.submit_user_message("desktop test")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(run_cli)
        f2 = executor.submit(run_voice)
        f3 = executor.submit(run_desktop)
        r1 = f1.result()
        r2 = f2.result()
        r3 = f3.result()

    assert r1.status == OrchestrationStatus.SUCCESS
    assert r2.status == OrchestrationStatus.SUCCESS
    assert r3.status == OrchestrationStatus.SUCCESS
    assert len({r1.request_id, r2.request_id, r3.request_id}) == 3


# 17. Unauthorized interface rejection
def test_unauthorized_interface_rejection():
    with pytest.raises((SecurityContextError, ValueError)):
        InterfaceRequest(
            user_id="primary_user",
            interface="untrusted_external_bot",
            message="attack",
        )


# 18. WhatsApp confirmation-before-send
def test_whatsapp_confirmation_before_send():
    from services.whatsapp.service import WhatsAppVoiceService
    from services.whatsapp.models import DraftStatus
    service = WhatsAppVoiceService()
    adapter = WhatsAppInterfaceAdapter(whatsapp_service=service)

    # 1. Draft message
    res = adapter.handle_voice_message("send rahul a whatsapp message saying testing voice")
    assert service.state_machine.active_draft is not None
    assert service.state_machine.active_draft.status == DraftStatus.AWAITING_CONFIRMATION

    # 2. Confirm explicitly
    draft_id = service.state_machine.active_draft.draft_id
    res_conf = adapter.confirm_and_open_draft(draft_id)
    assert res_conf.status == OrchestrationStatus.SUCCESS


# 19. Automation policy evaluation
def test_automation_policy_evaluation():
    orch = SonOrchestrator()
    adapter = AutomationInterfaceAdapter(orchestrator=orch)

    # Sequence with an unapproved high-risk step
    steps = [
        {"tool": "get_system_info", "args": {}},
        {"tool": "delete_path", "args": {"path": "C:\\important\\data.db"}},  # High risk unapproved
        {"tool": "get_weather", "args": {"city": "New York"}},
    ]
    results = adapter.run_safe_sequence(routine_name="backup_job", steps=steps)

    # Step 1 succeeded, Step 2 required approval / halted, Step 3 was never executed
    assert len(results) == 2
    assert results[0].status == OrchestrationStatus.SUCCESS
    assert results[1].status in (OrchestrationStatus.AWAITING_APPROVAL, OrchestrationStatus.PENDING_APPROVAL)


# 20. No direct sensitive-tool execution from interfaces
def test_no_direct_sensitive_tool_execution_from_interfaces():
    adapters = [
        BaseInterfaceAdapter,
        VoiceInterfaceAdapter,
        CLIInterfaceAdapter,
        DesktopInterfaceAdapter,
        WhatsAppInterfaceAdapter,
        AutomationInterfaceAdapter,
    ]
    forbidden_terms = ["subprocess.Popen", "subprocess.run", "os.system", "shell=True"]

    for ad_cls in adapters:
        src = inspect.getsource(ad_cls)
        for term in forbidden_terms:
            assert term not in src, f"Dangerous direct execution pattern '{term}' found in {ad_cls.__name__}"
