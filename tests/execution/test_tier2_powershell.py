# tests/execution/test_tier2_powershell.py — Tests for Tier 2 Controlled PowerShell & CLI Runner
import pytest
from core.execution.tier2_shell.powershell_runner import ControlledPowerShellRunner


@pytest.fixture
def runner():
    return ControlledPowerShellRunner()


def test_resolve_powershell(runner):
    ps = runner.get_powershell_executable()
    assert ps is not None
    assert "powershell.exe" in ps.lower() or "pwsh.exe" in ps.lower()


def test_run_process_git(runner):
    res = runner.run_process("git", ["--version"])
    assert res.success is True
    assert res.returncode == 0
    assert "git version" in res.stdout.lower()


def test_block_shell_chaining_in_args(runner):
    res = runner.run_process("git", ["status; rm -rf /"])
    assert res.success is False
    assert "Disallowed shell chain separator" in res.error_message


def test_block_arbitrary_powershell_tokens(runner):
    # Attempt to call Invoke-Expression
    res = runner.run_powershell_cmdlet("Invoke-Expression 'Get-Process'")
    assert res.success is False
    assert "Disallowed PowerShell cmdlet or token" in res.error_message


def test_block_downloadstring_attempt(runner):
    res = runner.run_powershell_cmdlet("Get-Process", params={"name": "(New-Object Net.WebClient).DownloadString"})
    assert res.success is False
    assert "Dangerous character in parameter value" in res.error_message


def test_run_template_git_status(runner):
    res = runner.run_template("git_status", cwd="C:\\AI\\SON")
    assert res.success is True
    assert res.returncode == 0


def test_run_template_invalid_id(runner):
    res = runner.run_template("non_existent_fake_template_999")
    assert res.success is False
    assert "not in the approved template registry" in res.error_message


def test_process_timeout_detection(runner):
    # Short timeout with ping to test timeout handling
    res = runner.run_process("powershell", ["-NoProfile", "-Command", "Start-Sleep -Seconds 5"], timeout_seconds=0.5)
    assert res.success is False
    assert res.timed_out is True
    assert "timed out" in res.error_message.lower()
