# tests/test_desktop_ipc.py — Unit and Integration Tests for Desktop Named Pipe IPC
import time
import json
import struct
import threading
import pytest

from services.ipc.protocol_dispatcher import ProtocolDispatcher
from services.ipc.named_pipe_server import NamedPipeServer, PIPE_NAME
from core.orchestrator import SonOrchestrator, OrchestratorResponse, OrchestrationStatus
from core.security.identity import identity_manager, UserRole
from core.security.session_manager import session_manager
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.policy import RiskTier


class MockOrchestrator:
    def process_request(self, text: str, context=None):
        return OrchestratorResponse(
            request_id=getattr(context, "request_id", "req_mock"),
            status=OrchestrationStatus.SUCCESS,
            response_text=f"Echo from orchestrator: {text}",
            tool_results=[],
        )


def test_protocol_dispatcher_ping():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    msg = {"action": "ping"}
    resp = dispatcher.dispatch(msg)
    assert resp["payload"]["status"] == "PONG"
    assert resp["payload"]["version"] == "3.0.0"
    assert resp["error"] is None


def test_protocol_dispatcher_handshake():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    msg = {
        "action": "handshake",
        "payload": {
            "client_version": "1.0.0",
            "client_type": "wpf_desktop",
            "requested_user_id": "usr_primary",
        },
    }
    resp = dispatcher.dispatch(msg)
    assert resp["payload"]["status"] == "AUTHENTICATED"
    assert resp["payload"]["user_id"] == "usr_primary"
    assert "session_id" in resp["payload"]
    assert "features_enabled" in resp["payload"]


def test_protocol_dispatcher_chat_send():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    # 1. Handshake first to create session
    h_resp = dispatcher.dispatch({
        "action": "handshake",
        "payload": {"requested_user_id": "usr_primary"},
    })
    session_id = h_resp["payload"]["session_id"]

    # 2. Send chat prompt
    chat_resp = dispatcher.dispatch({
        "action": "chat_send",
        "payload": {
            "prompt": "Hello SON Desktop!",
            "session_id": session_id,
            "user_id": "usr_primary",
        },
    })
    assert chat_resp["payload"]["status"] == "success"
    assert "Echo from orchestrator: Hello SON Desktop!" in chat_resp["payload"]["response"]


def test_protocol_dispatcher_hardware_telemetry():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    resp = dispatcher.dispatch({"action": "hardware_telemetry"})
    assert resp["payload"]["status"] == "SUCCESS"
    assert "cpu_percent" in resp["payload"]
    assert "ram_total_bytes" in resp["payload"]


def test_protocol_dispatcher_security_status():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    resp = dispatcher.dispatch({"action": "security_status"})
    assert resp["payload"]["status"] == "SECURE"
    assert resp["payload"]["policy_engine"] == "ACTIVE"
    assert "recent_events" in resp["payload"]


def test_protocol_dispatcher_memory():
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    # Add fact
    add_resp = dispatcher.dispatch({
        "action": "memory_add",
        "payload": {"fact": "Desktop test preference: Dark Mode", "category": "preferences"},
    })
    assert add_resp["payload"]["status"] == "SUCCESS"

    # List facts
    list_resp = dispatcher.dispatch({
        "action": "memory_list",
        "payload": {"category": "preferences"},
    })
    assert list_resp["payload"]["status"] == "SUCCESS"
    facts = [f["fact"] for f in list_resp["payload"]["facts"]]
    assert any("Dark Mode" in f for f in facts)


def test_named_pipe_server_roundtrip():
    """Verify live Windows Named Pipe server and client socket roundtrip."""
    pipe_test_name = r"\\.\pipe\son_desktop_ipc_test"
    dispatcher = ProtocolDispatcher(orchestrator=MockOrchestrator())
    server = NamedPipeServer(pipe_name=pipe_test_name, dispatcher=dispatcher)
    server.start()

    try:
        import win32file
        # Connect client to pipe
        time.sleep(0.1)
        client_handle = win32file.CreateFile(
            pipe_test_name,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )

        # Send Ping request with 4-byte length prefix
        req = {"action": "ping", "request_id": "req_roundtrip_01"}
        req_bytes = json.dumps(req).encode("utf-8")
        header = struct.pack(">I", len(req_bytes))
        win32file.WriteFile(client_handle, header + req_bytes)

        # Read 4-byte length prefix response
        _, resp_len_bytes = win32file.ReadFile(client_handle, 4)
        (resp_len,) = struct.unpack(">I", resp_len_bytes)
        _, resp_payload_bytes = win32file.ReadFile(client_handle, resp_len)

        resp_data = json.loads(resp_payload_bytes.decode("utf-8"))
        assert resp_data["request_id"] == "req_roundtrip_01"
        assert resp_data["payload"]["status"] == "PONG"

        win32file.CloseHandle(client_handle)
    finally:
        server.stop()


def test_real_orchestrator_ipc_dispatch():
    """Verify live ProtocolDispatcher wiring with actual SonOrchestrator instance."""
    class RealMockAgent:
        def __init__(self, output="SON V3 central orchestrator is fully operational."):
            self.output = output
        def run(self, user_prompt, session_id="default_session", context=None, message_history=None):
            class Result:
                def __init__(self, out):
                    self.output = out
            return Result(self.output)

    real_orchestrator = SonOrchestrator(pydantic_agent=RealMockAgent())
    dispatcher = ProtocolDispatcher(orchestrator=real_orchestrator)

    # 1. Handshake to authenticate and establish session
    h_resp = dispatcher.dispatch({
        "action": "handshake",
        "payload": {
            "client_version": "1.0.0",
            "client_type": "wpf_desktop",
            "requested_user_id": "usr_primary",
        },
    })
    assert h_resp["payload"]["status"] == "AUTHENTICATED"
    session_id = h_resp["payload"]["session_id"]
    user_id = h_resp["payload"]["user_id"]

    # 2. Dispatch a real chat turn through SonOrchestrator
    chat_resp = dispatcher.dispatch({
        "action": "chat_send",
        "payload": {
            "prompt": "Hello SON, what is your status?",
            "session_id": session_id,
            "user_id": user_id,
            "conversation_id": "conv_test_real",
        },
    })
    # Status should be success or valid orchestration response
    assert chat_resp["payload"]["status"] in ("success", "pending_approval", "blocked", "awaiting_approval")
    assert "operational" in chat_resp["payload"]["response"]
    assert chat_resp["error"] is None

