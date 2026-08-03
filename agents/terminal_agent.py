# agents/terminal_agent.py — Terminal & Shell Agent for SON V3
import subprocess
from core.config import Config, SecurityLevel


class TerminalAgent:
    """
    Executes shell commands, runs development servers, and manages terminal processes.
    """

    def __init__(self, router=None):
        self.router = router

    def execute_command(self, command: str, cwd: str = None) -> str:
        """Run a terminal command with security policy checks."""
        cmd_lower = command.strip().lower()

        # Security classification
        allowed = any(cmd_lower.startswith(w.lower()) for w in Config.TERMINAL_COMMAND_WHITELIST)
        level = SecurityLevel.SAFE if allowed else SecurityLevel.SENSITIVE

        if self.router and not self.router.check_permission("terminal_command", level, command):
            return f"Command '{command}' blocked by security policy."

        try:
            res = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
            )
            out = res.stdout.strip() or res.stderr.strip()
            return out if out else f"Command '{command}' executed successfully."
        except subprocess.TimeoutExpired:
            return f"Command '{command}' timed out."
        except Exception as e:
            return f"Command execution error: {e}"
