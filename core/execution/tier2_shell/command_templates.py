# core/execution/tier2_shell/command_templates.py — Controlled Command Templates
"""
Strict allowlisted command templates and parameter validators for Tier 2 execution.
All shell operations MUST match a registered template.
Arbitrary model-generated shell script strings are rejected outright.
"""
from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class CommandTemplate:
    """Definition of an approved, parameterized CLI / PowerShell template."""
    template_id: str
    executable_name: str              # e.g., 'git', 'docker', 'powershell', 'code', 'python'
    base_args: List[str]              # e.g., ['status'], ['ps', '--format']
    param_schema: Dict[str, type]     # parameter names and required Python types
    param_validators: Dict[str, Callable[[Any], Tuple[bool, str]]]
    description: str


# ── VALIDATORS ────────────────────────────────────────────────────────

def _validate_safe_identifier(val: Any) -> Tuple[bool, str]:
    """Validate branch names, container tags, remote names: alphanumeric with ._-/"""
    s = str(val).strip()
    if not s:
        return False, "Identifier cannot be empty."
    if s.startswith("-"):
        return False, "Leading hyphen/flag injection detected."
    if not re.match(r"^[a-zA-Z0-9_\-\.\/]+$", s):
        return False, f"Invalid characters in identifier: '{val}'."
    return True, ""


def _validate_safe_path(val: Any) -> Tuple[bool, str]:
    """Validate relative or absolute filesystem path."""
    s = str(val).strip()
    if not s:
        return False, "Path cannot be empty."
    if s.startswith("-"):
        return False, "Leading flag injection detected in path."
    # Disallow dangerous shell metacharacters: ;, |, &, `, $, <, >
    if re.search(r"[;&|`$<>]", s):
        return False, f"Dangerous shell metacharacters detected in path: '{val}'."
    return True, ""


def _validate_commit_message(val: Any) -> Tuple[bool, str]:
    """Validate git commit message."""
    s = str(val).strip()
    if not s:
        return False, "Commit message cannot be empty."
    if len(s) > 1000:
        return False, "Commit message exceeds 1000 characters."
    return True, ""


def _validate_positive_int(val: Any) -> Tuple[bool, str]:
    """Validate positive integer."""
    try:
        n = int(val)
        if n < 1:
            return False, "Value must be positive."
        if n > 10_000:
            return False, "Value exceeds maximum allowed limit."
        return True, ""
    except (ValueError, TypeError):
        return False, f"Expected integer, got '{val}'."


def _validate_container_id(val: Any) -> Tuple[bool, str]:
    """Validate Docker container ID or name."""
    s = str(val).strip()
    if not s:
        return False, "Container ID/name cannot be empty."
    if s.startswith("-"):
        return False, "Leading flag injection detected in container identifier."
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_\.\-]*$", s) or len(s) > 128:
        return False, f"Invalid container identifier: '{val}'."
    return True, ""


# ── MASTER COMMAND TEMPLATES ──────────────────────────────────────────

APPROVED_COMMAND_TEMPLATES: Dict[str, CommandTemplate] = {
    # ── Git Templates ───────────────────────────────────────────────
    "git_status": CommandTemplate(
        template_id="git_status",
        executable_name="git",
        base_args=["status", "--short", "--branch"],
        param_schema={},
        param_validators={},
        description="Inspect git working tree status",
    ),
    "git_log": CommandTemplate(
        template_id="git_log",
        executable_name="git",
        base_args=["log", "--oneline", "-n"],
        param_schema={"count": int},
        param_validators={"count": _validate_positive_int},
        description="View git commit log",
    ),
    "git_diff": CommandTemplate(
        template_id="git_diff",
        executable_name="git",
        base_args=["diff"],
        param_schema={"staged": bool},
        param_validators={},
        description="View git diff",
    ),
    "git_branch": CommandTemplate(
        template_id="git_branch",
        executable_name="git",
        base_args=["branch", "-a"],
        param_schema={},
        param_validators={},
        description="List all git branches",
    ),
    "git_remote": CommandTemplate(
        template_id="git_remote",
        executable_name="git",
        base_args=["remote", "-v"],
        param_schema={},
        param_validators={},
        description="Inspect git remotes",
    ),
    "git_add": CommandTemplate(
        template_id="git_add",
        executable_name="git",
        base_args=["add"],
        param_schema={"path": str},
        param_validators={"path": _validate_safe_path},
        description="Stage paths in git",
    ),
    "git_commit": CommandTemplate(
        template_id="git_commit",
        executable_name="git",
        base_args=["commit", "-m"],
        param_schema={"message": str},
        param_validators={"message": _validate_commit_message},
        description="Commit staged changes",
    ),
    "git_pull": CommandTemplate(
        template_id="git_pull",
        executable_name="git",
        base_args=["pull"],
        param_schema={"remote": str, "branch": str},
        param_validators={"remote": _validate_safe_identifier, "branch": _validate_safe_identifier},
        description="Pull commits from remote",
    ),
    "git_push": CommandTemplate(
        template_id="git_push",
        executable_name="git",
        base_args=["push"],
        param_schema={"remote": str, "branch": str},
        param_validators={"remote": _validate_safe_identifier, "branch": _validate_safe_identifier},
        description="Push commits to remote",
    ),

    # ── Docker Templates ────────────────────────────────────────────
    "docker_ps": CommandTemplate(
        template_id="docker_ps",
        executable_name="docker",
        base_args=["ps", "-a", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"],
        param_schema={},
        param_validators={},
        description="List Docker containers",
    ),
    "docker_images": CommandTemplate(
        template_id="docker_images",
        executable_name="docker",
        base_args=["images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}"],
        param_schema={},
        param_validators={},
        description="List Docker images",
    ),
    "docker_inspect": CommandTemplate(
        template_id="docker_inspect",
        executable_name="docker",
        base_args=["inspect"],
        param_schema={"container": str},
        param_validators={"container": _validate_container_id},
        description="Inspect Docker container details",
    ),
    "docker_start": CommandTemplate(
        template_id="docker_start",
        executable_name="docker",
        base_args=["start"],
        param_schema={"container": str},
        param_validators={"container": _validate_container_id},
        description="Start a Docker container",
    ),
    "docker_stop": CommandTemplate(
        template_id="docker_stop",
        executable_name="docker",
        base_args=["stop"],
        param_schema={"container": str},
        param_validators={"container": _validate_container_id},
        description="Stop a Docker container",
    ),
    "docker_restart": CommandTemplate(
        template_id="docker_restart",
        executable_name="docker",
        base_args=["restart"],
        param_schema={"container": str},
        param_validators={"container": _validate_container_id},
        description="Restart a Docker container",
    ),
    "docker_logs": CommandTemplate(
        template_id="docker_logs",
        executable_name="docker",
        base_args=["logs", "--tail"],
        param_schema={"container": str, "lines": int},
        param_validators={"container": _validate_container_id, "lines": _validate_positive_int},
        description="Fetch container logs",
    ),
    "docker_version": CommandTemplate(
        template_id="docker_version",
        executable_name="docker",
        base_args=["version", "--format", "json"],
        param_schema={},
        param_validators={},
        description="Check Docker version and daemon availability",
    ),

    # ── VS Code Templates ───────────────────────────────────────────
    "code_open_path": CommandTemplate(
        template_id="code_open_path",
        executable_name="code",
        base_args=[],
        param_schema={"path": str},
        param_validators={"path": _validate_safe_path},
        description="Open path in VS Code",
    ),
    "code_version": CommandTemplate(
        template_id="code_version",
        executable_name="code",
        base_args=["--version"],
        param_schema={},
        param_validators={},
        description="Get VS Code version",
    ),
    "code_list_extensions": CommandTemplate(
        template_id="code_list_extensions",
        executable_name="code",
        base_args=["--list-extensions"],
        param_schema={},
        param_validators={},
        description="List installed VS Code extensions",
    ),

    # ── Python / Dev Templates ──────────────────────────────────────
    "python_venv_create": CommandTemplate(
        template_id="python_venv_create",
        executable_name="python",
        base_args=["-m", "venv"],
        param_schema={"venv_path": str},
        param_validators={"venv_path": _validate_safe_path},
        description="Create virtual environment (.venv)",
    ),
    "python_pip_install": CommandTemplate(
        template_id="python_pip_install",
        executable_name="python",
        base_args=["-m", "pip", "install", "-r"],
        param_schema={"requirements_path": str},
        param_validators={"requirements_path": _validate_safe_path},
        description="Install dependencies from requirements.txt",
    ),
    "python_pytest_run": CommandTemplate(
        template_id="python_pytest_run",
        executable_name="python",
        base_args=["-m", "pytest", "-q"],
        param_schema={"test_path": str},
        param_validators={"test_path": _validate_safe_path},
        description="Run test suite safely",
    ),

    # ── Controlled PowerShell Cmdlet Templates ───────────────────────
    # Strictly structured read-only cmdlets — NEVER arbitrary ScriptBlocks
    "ps_get_service": CommandTemplate(
        template_id="ps_get_service",
        executable_name="powershell",
        base_args=["Get-Service"],
        param_schema={"name": str},
        param_validators={"name": _validate_safe_identifier},
        description="Get Windows service status",
    ),
    "ps_get_process": CommandTemplate(
        template_id="ps_get_process",
        executable_name="powershell",
        base_args=["Get-Process"],
        param_schema={"name": str},
        param_validators={"name": _validate_safe_identifier},
        description="Get process via PowerShell",
    ),
}


def get_template(template_id: str) -> Optional[CommandTemplate]:
    """Retrieve command template by ID."""
    return APPROVED_COMMAND_TEMPLATES.get(template_id)
