import subprocess
from pathlib import Path
from core.config import SecurityLevel
from plugins.base import BasePlugin


class VSCodePlugin(BasePlugin):
    """
    Manages VS Code projects, virtual environments, dependency installation, and git workflows.
    """

    def __init__(self):
        super().__init__(name="vscode", description="VS Code workspace & Python environment manager", category="coding")

    def initialize(self):
        self.register_tool(
            "open_vscode_project", self.open_vscode_project,
            description="Open a project or workspace directory in VS Code",
            params={"path": {"type": "string", "description": "Project directory path"}},
            required=["path"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "create_venv", self.create_venv,
            description="Create a Python virtual environment (.venv) in a project folder",
            params={"project_path": {"type": "string", "description": "Project directory path"}},
            required=["project_path"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "install_requirements", self.install_requirements,
            description="Install Python dependencies from requirements.txt",
            params={"project_path": {"type": "string", "description": "Project directory path"}},
            required=["project_path"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "git_commit_changes", self.git_commit_changes,
            description="Stage changes and commit them with a message in git",
            params={
                "project_path": {"type": "string", "description": "Project directory path"},
                "message": {"type": "string", "description": "Commit message"}
            },
            required=["project_path", "message"], security_level=SecurityLevel.SENSITIVE
        )

    # ── Implementations ───────────────────────────────────────

    def open_vscode_project(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Project path '{path}' does not exist."
        try:
            subprocess.Popen(f'code "{p}"', shell=True)
            return f"Opened project '{p.name}' in VS Code."
        except Exception as e:
            return f"Failed to open VS Code: {e}"

    def create_venv(self, project_path: str) -> str:
        p = Path(project_path)
        if not p.exists():
            return f"Project directory '{project_path}' not found."
        venv_path = p / ".venv"
        if venv_path.exists():
            return f"Virtual environment already exists at '{venv_path}'."
        try:
            res = subprocess.run(["python", "-m", "venv", str(venv_path)], capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                return f"Created virtual environment (.venv) in '{p.name}'."
            return f"Failed to create venv: {res.stderr}"
        except Exception as e:
            return f"Error creating venv: {e}"

    def install_requirements(self, project_path: str) -> str:
        p = Path(project_path)
        req_file = p / "requirements.txt"
        if not req_file.exists():
            return f"requirements.txt not found in '{project_path}'."

        import sys
        pip_exe = p / ".venv" / "Scripts" / "pip.exe"
        if pip_exe.exists():
            cmd = [str(pip_exe), "install", "-r", str(req_file)]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if res.returncode == 0:
                return f"Installed requirements for '{p.name}' successfully."
            return f"Pip install failed: {res.stderr[:300]}"
        except Exception as e:
            return f"Error running pip install: {e}"

    def git_commit_changes(self, project_path: str, message: str) -> str:
        p = Path(project_path)
        if not (p / ".git").exists():
            return f"Not a git repository: '{project_path}'."
        try:
            subprocess.run(["git", "add", "."], cwd=p, check=True)
            res = subprocess.run(["git", "commit", "-m", message], cwd=p, capture_output=True, text=True)
            return f"Git commit completed: {res.stdout.strip()}"
        except subprocess.CalledProcessError as e:
            return f"Git commit failed: {e}"
