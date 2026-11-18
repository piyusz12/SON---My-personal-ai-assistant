# tests/execution/test_execution_timeouts.py — Tests for Execution Timeouts & Cancellation
import time
import pytest
from core.execution.execution_context import ExecutionContext
from core.execution.execution_router import execution_router
from core.execution.execution_result import ExecutionStatus
from core.execution.tier2_shell.powershell_runner import controlled_shell


def test_context_expiration():
    ctx = ExecutionContext(timeout_seconds=0.05)
    assert ctx.is_expired() is False
    time.sleep(0.06)
    assert ctx.is_expired() is True


def test_router_rejects_expired_context():
    ctx = ExecutionContext(timeout_seconds=0.01)
    time.sleep(0.02)
    res = execution_router.route("list_directory", {"path": "C:\\AI"}, context=ctx)
    assert res.status == ExecutionStatus.TIMEOUT


def test_powershell_runner_timeout():
    # Run sleep command with 0.3s timeout
    res = controlled_shell.run_process("powershell", ["-NoProfile", "-Command", "Start-Sleep -Seconds 3"], timeout_seconds=0.3)
    assert res.success is False
    assert res.timed_out is True
    assert res.duration_ms < 3000
