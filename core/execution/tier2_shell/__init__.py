# core/execution/tier2_shell/__init__.py — Tier 2 Controlled Shell Adapter
"""
Tier 2 Controlled Shell & CLI Operations Adapter.
All execution passes through the ControlledPowerShellRunner, enforcing:
  - shell=False
  - Executable allowlist
  - Command templates
  - Typed sub-runners (git_runner, docker_runner, vscode_runner)
"""
import logging
import time
from typing import Any, Dict, Optional

from core.execution.execution_context import ExecutionContext
from core.execution.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    TierLevel,
)
from core.execution.tier2_shell.docker_runner import docker_runner
from core.execution.tier2_shell.executable_registry import executable_registry
from core.execution.tier2_shell.git_runner import git_runner
from core.execution.tier2_shell.powershell_runner import controlled_shell
from core.execution.tier2_shell.vscode_runner import vscode_runner

logger = logging.getLogger(__name__)


class ShellTier:
    """Tier 2: Controlled PowerShell & CLI Adapter."""

    def __init__(self):
        self.shell = controlled_shell
        self.registry = executable_registry
        self.git = git_runner
        self.docker = docker_runner
        self.vscode = vscode_runner

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """Execute a tool through the controlled Tier 2 shell engine."""
        start = time.perf_counter()
        ctx = context or ExecutionContext()
        output: Any = None
        error: Optional[str] = None
        status = ExecutionStatus.SUCCESS

        try:
            # ── Git Operations ───────────────────────────────────────
            if tool_name == "git_status":
                res = self.git.status(repo_path=arguments.get("repo_path") or arguments.get("project_path") or ctx.working_directory)
            elif tool_name == "git_log":
                res = self.git.log(
                    repo_path=arguments.get("repo_path") or ctx.working_directory,
                    max_count=int(arguments.get("max_count", 10)),
                )
            elif tool_name == "git_diff":
                res = self.git.diff(
                    repo_path=arguments.get("repo_path") or ctx.working_directory,
                    staged=arguments.get("staged", False),
                )
            elif tool_name == "git_branch":
                res = self.git.branch(repo_path=arguments.get("repo_path") or ctx.working_directory)
            elif tool_name == "git_remote":
                res = self.git.remote(repo_path=arguments.get("repo_path") or ctx.working_directory)
            elif tool_name == "git_add":
                res = self.git.add(
                    repo_path=arguments.get("repo_path") or ctx.working_directory,
                    path=arguments.get("path", "."),
                )
            elif tool_name in ("git_commit", "git_commit_changes"):
                # If path specified without commit first, add then commit
                repo = arguments.get("repo_path") or arguments.get("project_path") or ctx.working_directory
                if tool_name == "git_commit_changes":
                    self.git.add(repo, ".")
                res = self.git.commit(repo_path=repo, message=arguments.get("message", ""))
            elif tool_name == "git_pull":
                res = self.git.pull(
                    repo_path=arguments.get("repo_path") or ctx.working_directory,
                    remote=arguments.get("remote", "origin"),
                    branch=arguments.get("branch"),
                )
            elif tool_name == "git_push":
                res = self.git.push(
                    repo_path=arguments.get("repo_path") or ctx.working_directory,
                    remote=arguments.get("remote", "origin"),
                    branch=arguments.get("branch"),
                )

            # ── Docker Operations ────────────────────────────────────
            elif tool_name in ("docker_list_containers", "docker_ps"):
                res = self.docker.list_containers(all_containers=arguments.get("all_containers", True))
            elif tool_name in ("docker_list_images", "docker_images"):
                res = self.docker.list_images()
            elif tool_name in ("docker_inspect_container", "docker_inspect"):
                res = self.docker.inspect_container(container=arguments.get("container", ""))
            elif tool_name in ("docker_start", "docker_start_container"):
                res = self.docker.start_container(container=arguments.get("container", ""))
            elif tool_name in ("docker_stop", "docker_stop_container"):
                res = self.docker.stop_container(
                    container=arguments.get("container", ""),
                    timeout_seconds=int(arguments.get("timeout", 10)),
                )
            elif tool_name in ("docker_restart", "docker_restart_container"):
                res = self.docker.restart_container(container=arguments.get("container", ""))
            elif tool_name == "docker_logs":
                res = self.docker.logs(
                    container=arguments.get("container", ""),
                    lines=int(arguments.get("lines", 50)),
                )
            elif tool_name in ("docker_check_status", "docker_status"):
                res = self.docker.check_status()
            elif tool_name == "docker_build":
                res = self.docker.build_image(
                    dockerfile_path=arguments.get("dockerfile_path", "Dockerfile"),
                    tag=arguments.get("tag"),
                )

            # ── VS Code & Dev Environment ────────────────────────────
            elif tool_name in ("open_vscode", "open_vscode_project"):
                res = self.vscode.open_path(
                    target_path=arguments.get("path") or arguments.get("project_path") or ctx.working_directory
                )
            elif tool_name == "open_vscode_file":
                res = self.vscode.open_file(
                    file_path=arguments.get("file_path", ""),
                    line=arguments.get("line"),
                )
            elif tool_name == "check_project_structure":
                res = self.vscode.check_project_structure(
                    project_path=arguments.get("project_path", ctx.working_directory)
                )
            elif tool_name == "create_venv":
                res = self.vscode.create_venv(
                    project_path=arguments.get("project_path", ctx.working_directory)
                )
            elif tool_name in ("install_requirements", "pip_install"):
                res = self.vscode.install_requirements(
                    project_path=arguments.get("project_path", ctx.working_directory)
                )
            elif tool_name == "run_tests":
                res = self.vscode.run_tests(
                    project_path=arguments.get("project_path", ctx.working_directory),
                    test_path=arguments.get("test_path"),
                )

            # ── PowerShell Cmdlet Execution ──────────────────────────
            elif tool_name == "run_powershell_cmdlet":
                cmdlet = arguments.get("cmdlet", "")
                params = arguments.get("params", {})
                pres = self.shell.run_powershell_cmdlet(
                    cmdlet=cmdlet,
                    params=params,
                    cwd=ctx.working_directory,
                    timeout_seconds=ctx.timeout_seconds,
                )
                res = {
                    "success": pres.success,
                    "output": pres.stdout or pres.stderr,
                    "returncode": pres.returncode,
                    "error": pres.error_message,
                }
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    error=f"Tool '{tool_name}' not implemented in Tier 2 Shell adapter.",
                    tier_used=TierLevel.TIER2_SHELL,
                    tool_name=tool_name,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            if isinstance(res, dict) and not res.get("success", True):
                status = ExecutionStatus.FAILURE
                error = res.get("error", "Unknown shell tier error")
                output = res
            else:
                status = ExecutionStatus.SUCCESS
                output = res

        except Exception as e:
            logger.exception(f"Unhandled error in Tier 2 execution for '{tool_name}': {e}")
            status = ExecutionStatus.FAILURE
            error = str(e)

        duration_ms = (time.perf_counter() - start) * 1000
        return ExecutionResult(
            status=status,
            output=output,
            error=error,
            tier_used=TierLevel.TIER2_SHELL,
            tool_name=tool_name,
            duration_ms=duration_ms,
            verified=(status == ExecutionStatus.SUCCESS),
        )


__all__ = [
    "ShellTier",
    "controlled_shell",
    "executable_registry",
    "git_runner",
    "docker_runner",
    "vscode_runner",
]
