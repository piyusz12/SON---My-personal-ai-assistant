# tests/execution/test_execution_permissions.py — Tests for Permission & Approval Gates
import pytest
from core.execution.execution_policy import (
    get_policy,
    READ,
    LOCAL_REVERSIBLE,
    HIGH_IMPACT,
    DENIED,
    APPROVAL_REQUIRED_OPERATIONS,
)
from core.execution.execution_router import execution_router
from core.execution.execution_result import ExecutionStatus


def test_read_operations_require_no_approval():
    for op in ["list_directory", "read_file", "search_files", "git_status", "get_system_info"]:
        pol = get_policy(op)
        assert pol.permission_level == READ
        assert pol.requires_approval is False


def test_high_impact_operations_require_approval():
    for op in ["delete_file", "delete_directory", "git_push", "git_pull", "shutdown_pc", "restart_pc"]:
        pol = get_policy(op)
        assert pol.permission_level == HIGH_IMPACT
        assert pol.requires_approval is True
        assert op in APPROVAL_REQUIRED_OPERATIONS


def test_git_push_approval_policy():
    pol = get_policy("git_push")
    assert pol.requires_approval is True
    assert pol.permission_level == HIGH_IMPACT


def test_delete_path_approval_policy():
    pol = get_policy("delete_path")
    assert pol.requires_approval is True
    assert pol.permission_level == HIGH_IMPACT


def test_denied_operations_are_blocked_at_router():
    for denied_op in ["format_drive", "bypass_execution_policy", "arbitrary_powershell"]:
        res = execution_router.route(denied_op, {})
        assert res.status == ExecutionStatus.DENIED
        assert "DENIED" in res.error
