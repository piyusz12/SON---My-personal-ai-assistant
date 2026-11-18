# tests/execution/test_tier1_process.py — Tests for Tier 1 Process & App Management
from unittest.mock import patch, MagicMock
import pytest
from core.execution.tier1_native.process import NativeProcessManager, APPROVED_APP_DISCOVERY


@pytest.fixture
def process_mgr():
    return NativeProcessManager()


def test_resolve_app_key(process_mgr):
    assert process_mgr.resolve_app_key("vs code") == "vscode"
    assert process_mgr.resolve_app_key("Google Chrome") == "chrome"
    assert process_mgr.resolve_app_key("calc") == "calculator"


def test_is_app_approved(process_mgr):
    assert process_mgr.is_app_approved("chrome") is True
    assert process_mgr.is_app_approved("vscode") is True
    assert process_mgr.is_app_approved("notepad") is True
    assert process_mgr.is_app_approved("malware.exe") is False


def test_find_executable_notepad(process_mgr):
    exe = process_mgr.find_executable("notepad")
    assert exe is not None
    assert "notepad.exe" in exe.lower()


def test_block_unapproved_app_launch(process_mgr):
    res = process_mgr.launch_app("unapproved_hack_tool.exe")
    assert res["success"] is False
    assert "Security Error" in res["error"]


def test_is_app_running_check(process_mgr):
    res = process_mgr.is_app_running("explorer")
    assert res["success"] is True
    assert isinstance(res["running"], bool)


def test_list_processes(process_mgr):
    res = process_mgr.list_processes(limit=5)
    assert res["success"] is True
    assert len(res["processes"]) <= 5
    assert res["total_running"] > 0


def test_get_process_info_query(process_mgr):
    res = process_mgr.get_process_info("explorer")
    assert res["success"] is True
    assert "processes" in res
