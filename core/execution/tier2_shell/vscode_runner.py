# core/execution/tier2_shell/vscode_runner.py — Tier 2 VS Code & Dev Environment Runner
"""
Controlled VS Code workspace, Python virtual environment, dependencies,
and automated test execution engine.
Enforces canonical path safety and prevents host python environment contamination.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.execution.tier2_shell.powershell_runner import controlled_shell

logger = logging.getLogger(__name__)


class VSCodeRunner:
    """Tier 2 Developer Environment & VS Code Automation."""

    def __init__(self, runner=None):
        self.runner = runner or controlled_shell

    def open_path(self, target_path: Union[str, Path] = "C:\\AI") -> Dict[str, Any]:
        """Open a file, project, or workspace in VS Code."""
        p = Path(target_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"Target path '{target_path}' does not exist."}

        res = self.runner.run_process("code", [str(p)], timeout_seconds=15.0)
        return {
            "success": res.success,
            "path": str(p),
            "message": f"Opened '{p.name}' in VS Code." if res.success else f"Failed to launch VS Code: {res.stderr}",
            "error": res.error_message,
        }

    def open_file(self, file_path: Union[str, Path], line: Optional[int] = None) -> Dict[str, Any]:
        """Open a specific file in VS Code at an optional line number."""
        p = Path(file_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        target_arg = f"{p}:{line}" if line else str(p)
        args = ["-g", target_arg] if line else [str(p)]

        res = self.runner.run_process("code", args, timeout_seconds=15.0)
        return {
            "success": res.success,
            "path": str(p),
            "line": line,
            "message": f"Opened '{p.name}' in VS Code.",
            "error": res.error_message,
        }

    def check_project_structure(self, project_path: Union[str, Path] = "C:\\AI\\SON") -> Dict[str, Any]:
        """Inspect key project markers: venv, git, requirements.txt, pyproject.toml."""
        p = Path(project_path).resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "error": f"Project directory '{project_path}' does not exist."}

        has_git = (p / ".git").exists()
        has_venv = (p / ".venv").exists()
        has_reqs = (p / "requirements.txt").exists()
        has_pyproject = (p / "pyproject.toml").exists()
        has_tests = (p / "tests").exists()

        top_files = [e.name for e in p.iterdir() if not e.name.startswith(".")][:20]

        return {
            "success": True,
            "project_name": p.name,
            "project_path": str(p),
            "has_git": has_git,
            "has_venv": has_venv,
            "has_requirements": has_reqs,
            "has_pyproject": has_pyproject,
            "has_tests": has_tests,
            "top_level_files": top_files,
        }

    def create_venv(self, project_path: Union[str, Path]) -> Dict[str, Any]:
        """Create a dedicated Python virtual environment (.venv) inside the project."""
        p = Path(project_path).resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "error": f"Project directory '{project_path}' does not exist."}

        venv_path = p / ".venv"
        if venv_path.exists():
            return {
                "success": True,
                "message": f"Virtual environment already exists at '{venv_path}'.",
                "venv_path": str(venv_path),
            }

        res = self.runner.run_process("python", ["-m", "venv", str(venv_path)], cwd=p, timeout_seconds=60.0)
        return {
            "success": res.success,
            "venv_path": str(venv_path),
            "message": f"Created virtual environment in '{p.name}'." if res.success else f"Failed to create venv: {res.stderr}",
            "error": res.error_message,
        }

    def install_requirements(self, project_path: Union[str, Path]) -> Dict[str, Any]:
        """Install dependencies from requirements.txt into the project's .venv."""
        p = Path(project_path).resolve()
        req_file = p / "requirements.txt"
        if not req_file.exists():
            return {"success": False, "error": f"requirements.txt not found in '{project_path}'."}

        # Resolve pip inside .venv strictly to prevent host corruption
        pip_exe = p / ".venv" / "Scripts" / "pip.exe"
        if not pip_exe.exists():
            pip_exe = p / ".venv" / "bin" / "pip"

        if not pip_exe.exists():
            return {
                "success": False,
                "error": f"Security Error: Virtual environment (.venv) not found in '{p.name}'. Please create one first using create_venv to prevent host python corruption.",
            }

        res = self.runner.run_process(
            str(pip_exe),
            ["install", "-r", str(req_file)],
            cwd=p,
            timeout_seconds=180.0,
        )
        return {
            "success": res.success,
            "output": res.stdout if res.success else res.stderr,
            "error": res.error_message,
            "message": f"Installed requirements for '{p.name}'." if res.success else "Failed to install requirements.",
        }

    def run_tests(self, project_path: Union[str, Path] = "C:\\AI\\SON", test_path: Optional[str] = None) -> Dict[str, Any]:
        """Run pytest suite inside the target project."""
        p = Path(project_path).resolve()
        args = ["-m", "pytest", "-q"]
        if test_path:
            args.append(test_path)

        res = self.runner.run_process("python", args, cwd=p, timeout_seconds=180.0)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "error": res.error_message,
        }


# Singleton instance
vscode_runner = VSCodeRunner()
