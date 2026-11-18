# core/execution/tier2_shell/git_runner.py — Tier 2 Typed Git Operations
"""
Typed, deterministic Git integration via ControlledPowerShellRunner.
Never invokes raw bash/shell scripts; executes explicit argument arrays.
READ operations are automated; state-mutating operations enforce risk policies.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.execution.tier2_shell.powershell_runner import controlled_shell

logger = logging.getLogger(__name__)


class GitRunner:
    """Tier 2 Typed Git Operations Runner."""

    def __init__(self, runner=None):
        self.runner = runner or controlled_shell

    def status(self, repo_path: Union[str, Path] = "C:\\AI\\SON") -> Dict[str, Any]:
        """Get git working tree status (READ)."""
        res = self.runner.run_process("git", ["status", "--short", "--branch"], cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def log(self, repo_path: Union[str, Path] = "C:\\AI\\SON", max_count: int = 10) -> Dict[str, Any]:
        """Get recent git commit log (READ)."""
        count = max(1, min(100, int(max_count)))
        res = self.runner.run_process("git", ["log", "--oneline", "-n", str(count)], cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def diff(self, repo_path: Union[str, Path] = "C:\\AI\\SON", staged: bool = False) -> Dict[str, Any]:
        """Inspect git diff (READ)."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        res = self.runner.run_process("git", args, cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout if res.stdout else "No changes.",
            "repo_path": str(repo_path),
            "staged": staged,
            "error": res.error_message,
        }

    def branch(self, repo_path: Union[str, Path] = "C:\\AI\\SON") -> Dict[str, Any]:
        """List git branches (READ)."""
        res = self.runner.run_process("git", ["branch", "-a"], cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def remote(self, repo_path: Union[str, Path] = "C:\\AI\\SON") -> Dict[str, Any]:
        """List git remotes (READ)."""
        res = self.runner.run_process("git", ["remote", "-v"], cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def add(self, repo_path: Union[str, Path] = "C:\\AI\\SON", path: str = ".") -> Dict[str, Any]:
        """Stage files in git (LOCAL_REVERSIBLE)."""
        clean_path = path.strip() if path else "."
        # Guard against flag injection
        if clean_path.startswith("-"):
            return {"success": False, "error": "Invalid path for git add."}

        res = self.runner.run_process("git", ["add", clean_path], cwd=repo_path)
        return {
            "success": res.success,
            "output": f"Staged '{clean_path}'." if res.success else res.stderr,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def commit(self, repo_path: Union[str, Path] = "C:\\AI\\SON", message: str = "") -> Dict[str, Any]:
        """
        Commit staged changes (LOCAL_REVERSIBLE / approval).
        Requires explicit commit message.
        """
        clean_msg = message.strip()
        if not clean_msg:
            return {"success": False, "error": "Commit message cannot be empty."}

        res = self.runner.run_process("git", ["commit", "-m", clean_msg], cwd=repo_path)
        return {
            "success": res.success,
            "output": res.stdout if res.success else res.stderr,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def pull(
        self,
        repo_path: Union[str, Path] = "C:\\AI\\SON",
        remote: str = "origin",
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pull remote changes (HIGH_IMPACT / approval)."""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        res = self.runner.run_process("git", args, cwd=repo_path, timeout_seconds=60.0)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }

    def push(
        self,
        repo_path: Union[str, Path] = "C:\\AI\\SON",
        remote: str = "origin",
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Push commits to remote (HIGH_IMPACT / explicit confirmation)."""
        args = ["push", remote]
        if branch:
            args.append(branch)
        res = self.runner.run_process("git", args, cwd=repo_path, timeout_seconds=60.0)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "repo_path": str(repo_path),
            "error": res.error_message,
        }


# Singleton instance
git_runner = GitRunner()
