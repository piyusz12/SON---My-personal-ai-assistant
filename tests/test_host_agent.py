# tests/test_host_agent.py — Comprehensive Unit & Integration Tests for HostAgent and EventBus
import time
import pytest
from unittest.mock import MagicMock, patch

from core.host_agent import HostAgent, host_agent
from core.event_bus import EventBus, event_bus, EventType, SonEvent
from core.interfaces.contract import InterfaceRequest, InterfaceResponse, OrchestrationStatus
from core.security.context import SecurityContext, create_trusted_context
from core.security.policy import RiskTier
from core.intent_router import IntentType, IntentResult


@pytest.fixture
def clean_event_bus():
    event_bus.clear()
    yield event_bus
    event_bus.clear()


def test_event_bus_publish_and_subscribe(clean_event_bus):
    received = []

    def handler(event: SonEvent):
        received.append(event)

    clean_event_bus.subscribe(EventType.TOOL_STARTED, handler)

    clean_event_bus.publish(EventType.TOOL_STARTED, {"tool_name": "open_application"}, source="test")
    clean_event_bus.publish(EventType.TOOL_COMPLETED, {"tool_name": "open_application"}, source="test")

    # Only TOOL_STARTED should be received by specific subscriber
    assert len(received) == 1
    assert received[0].event_type == EventType.TOOL_STARTED
    assert received[0].payload["tool_name"] == "open_application"


def test_event_bus_global_subscriber(clean_event_bus):
    all_events = []

    def global_handler(event: SonEvent):
        all_events.append(event)

    clean_event_bus.subscribe_all(global_handler)

    clean_event_bus.publish(EventType.REQUEST_RECEIVED, {"msg": "hi"})
    clean_event_bus.publish(EventType.REQUEST_COMPLETED, {"status": "success"})

    assert len(all_events) == 2
    assert all_events[0].event_type == EventType.REQUEST_RECEIVED
    assert all_events[1].event_type == EventType.REQUEST_COMPLETED


def test_host_agent_singleton():
    ha1 = HostAgent()
    ha2 = HostAgent()
    assert ha1 is ha2
    assert ha1 is host_agent


def test_host_agent_status():
    status = host_agent.get_status()
    assert status["version"] == "3.0.0"
    assert status["host_agent"] == "ONLINE"
    assert "gpu" in status
    assert "registered_tools" in status


def test_host_agent_process_request_empty_message():
    resp = host_agent.process_request("", user_id="primary_user")
    assert resp.status == OrchestrationStatus.SUCCESS
    assert resp.response_text == ""


def test_host_agent_process_request_unauthorized_user():
    # user_id must be non-empty string
    resp = host_agent.process_request("hello", user_id="")
    assert resp.status == OrchestrationStatus.AUTHENTICATION_ERROR
    assert "User ID" in resp.response_text


def test_host_agent_command_intent_bypasses_semantic_memory(clean_event_bus):
    # For a deterministic command (e.g. "open chrome"), L3 semantic memory should not be queried
    events = []
    clean_event_bus.subscribe_all(lambda ev: events.append(ev))

    with patch.object(host_agent.intent_router, "classify") as mock_classify:
        mock_classify.return_value = IntentResult(
            intent=IntentType.COMMAND,
            confidence=0.98,
            needs_memory=False,
            needs_codebase=False,
            needs_tools=True,
            subcategory="app_control",
        )
        with patch.object(host_agent.memory, "build_context") as mock_mem:
            mock_mem.return_value = ""
            with patch.object(host_agent.orchestrator, "process_request") as mock_orch:
                from core.orchestrator import OrchestratorResponse
                mock_orch.return_value = OrchestratorResponse(
                    request_id="req_test",
                    status=OrchestrationStatus.SUCCESS,
                    response_text="Opened Chrome.",
                )

                resp = host_agent.process_request("open chrome", user_id="primary_user", interface="cli")
                assert resp.status == OrchestrationStatus.SUCCESS
                assert resp.response_text == "Opened Chrome."

                # Verify semantic memory was called with include_semantic=False
                mock_mem.assert_called_once_with("open chrome", include_semantic=False)

    # Verify event trail
    event_types = [ev.event_type for ev in events]
    assert EventType.REQUEST_RECEIVED in event_types
    assert EventType.THINKING in event_types
    assert EventType.REQUEST_COMPLETED in event_types


def test_host_agent_complex_intent_queries_semantic_memory():
    with patch.object(host_agent.intent_router, "classify") as mock_classify:
        mock_classify.return_value = IntentResult(
            intent=IntentType.COMPLEX,
            confidence=0.95,
            needs_memory=True,
            needs_codebase=True,
            needs_tools=True,
        )
        with patch.object(host_agent.memory, "build_context") as mock_mem:
            mock_mem.return_value = "[RELEVANT HISTORICAL CONTEXT]\n- User is working on AI."
            with patch.object(host_agent.orchestrator, "process_request") as mock_orch:
                from core.orchestrator import OrchestratorResponse
                mock_orch.return_value = OrchestratorResponse(
                    request_id="req_test2",
                    status=OrchestrationStatus.SUCCESS,
                    response_text="Analyzed code.",
                )

                resp = host_agent.process_request("Refactor my agent architecture", user_id="primary_user")
                assert resp.status == OrchestrationStatus.SUCCESS
                mock_mem.assert_called_once_with("Refactor my agent architecture", include_semantic=True)


def test_host_agent_execute_action_direct():
    ctx = create_trusted_context(user_id="primary_user", interface_type="test")
    with patch.object(host_agent.orchestrator, "execute_action") as mock_exec:
        from core.orchestrator import ActionResult
        mock_exec.return_value = ActionResult(
            success=True,
            output="Done",
            tool_name="test_tool",
            risk_tier="low",
        )

        res = host_agent.execute_action("test_tool", {"param": 1}, context=ctx)
        assert res.success is True
        assert res.output == "Done"
        mock_exec.assert_called_once_with(
            tool_name="test_tool",
            arguments={"param": 1},
            context=ctx,
            approval_id=None,
        )


def test_host_agent_resolve_approval():
    with patch.object(host_agent.orchestrator, "handle_approval") as mock_res:
        from core.orchestrator import OrchestratorResponse
        mock_res.return_value = OrchestratorResponse(
            request_id="req_appr",
            status=OrchestrationStatus.SUCCESS,
            response_text="Executed after approval",
        )

        res = host_agent.resolve_approval("appr_12345", decision=True, user_id="primary_user")
        assert res.status == OrchestrationStatus.SUCCESS
        assert res.response_text == "Executed after approval"
        mock_res.assert_called_once()
