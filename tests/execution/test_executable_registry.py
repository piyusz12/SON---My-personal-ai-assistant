# tests/execution/test_executable_registry.py — Tests for Centralized Executable Registry
import pytest
from core.execution.tier2_shell.executable_registry import ExecutableRegistry


@pytest.fixture
def registry():
    return ExecutableRegistry()


def test_baseline_executables_registered(registry):
    for name in ["powershell", "python", "git", "docker", "code", "wt", "notepad", "calc"]:
        assert registry.is_approved(name) is True, f"Expected {name} to be approved"


def test_unapproved_executable_rejected(registry):
    assert registry.is_approved("mimikatz.exe") is False
    assert registry.is_approved("nc.exe") is False
    assert registry.is_approved("curl.exe") is False
    assert registry.is_approved("cmd.exe") is False


def test_resolve_executable_notepad(registry):
    resolved = registry.resolve_executable("notepad")
    assert resolved is not None
    assert "notepad.exe" in resolved.lower()


def test_resolve_executable_git(registry):
    resolved = registry.resolve_executable("git")
    assert resolved is not None
    assert "git.exe" in resolved.lower()


def test_resolve_unapproved_returns_none(registry):
    resolved = registry.resolve_executable("unauthorized_binary")
    assert resolved is None


def test_list_approved(registry):
    approved = registry.list_approved()
    assert len(approved) >= 8
    names = [a["canonical_name"] for a in approved]
    assert "git" in names
    assert "powershell" in names
