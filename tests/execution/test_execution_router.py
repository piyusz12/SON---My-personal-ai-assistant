# tests/execution/test_execution_router.py — Tests for Central ExecutionRouter
import pytest
from core.execution.execution_router import ExecutionRouter
from core.execution.execution_result import ExecutionStatus, TierLevel
from core.execution.execution_context import ExecutionContext
from core.execution.execution_policy import DENIED, HIGH_IMPACT, READ


@pytest.fixture
def router():
    r = ExecutionRouter()
    r.initialize()
    return r


def test_router_initialization(router):
    assert router._tier1 is not None
    assert router._tier2 is not None


def test_route_tier1_read(router):
    res = router.route("list_directory", {"path": "C:\\AI"})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.tier_used == TierLevel.TIER1_NATIVE
    assert res.routing_decision is not None
    assert res.routing_decision.permission_level == READ
    assert res.verified is True


def test_route_tier2_git_status(router):
    res = router.route("git_status", {"repo_path": "C:\\AI\\SON"})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.tier_used == TierLevel.TIER2_SHELL
    assert res.routing_decision.permission_level == READ


def test_route_tier3_unavailable(router):
    res = router.route("click_ui_element", {"element_id": "btn_save"})
    assert res.status == ExecutionStatus.UNAVAILABLE
    assert res.tier_used == TierLevel.TIER3_UIA
    assert "Tier 3 (Windows UI Automation) is not yet implemented" in res.error


def test_route_tier4_unavailable(router):
    res = router.route("visual_identify", {"target": "save_icon"})
    assert res.status == ExecutionStatus.UNAVAILABLE
    assert res.tier_used == TierLevel.TIER4_VISUAL
    assert "Tier 4 (Visual Computer Use) is not yet implemented" in res.error


def test_route_denied_operation(router):
    res = router.route("format_drive", {"drive": "C:"})
    assert res.status == ExecutionStatus.DENIED
    assert "DENIED" in res.error


def test_route_expired_context(router):
    ctx = ExecutionContext(timeout_seconds=0.001)
    import time
    time.sleep(0.005)
    res = router.route("get_system_info", {}, context=ctx)
    assert res.status == ExecutionStatus.TIMEOUT
    assert "expired" in res.error.lower()
