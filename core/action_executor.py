# core/action_executor.py — Central Execution Gateway for SON
"""
All tool calls flow through ActionExecutor, which provides:
  1. Live action visibility — Rich panels showing what SON is doing
  2. Security level checking — SAFE/MEDIUM/SENSITIVE/CRITICAL classification
  3. Interactive confirmation — Dad approves dangerous actions before execution
  4. Action logging — Every action logged with timing and result

Inspired by Antigravity IDE's permission model.

Usage:
    executor = ActionExecutor(ui=terminal_ui)
    result = executor.execute("kill_process", {"name": "chrome"}, tool_func, security_level)
"""
import time
import json
import logging
from typing import Callable, Any

from core.config import Config, SecurityLevel

logger = Config.get_logger(__name__)
tools_logger = Config.get_named_logger("son.tools", "tools")

# Security level display configuration
SECURITY_DISPLAY = {
    SecurityLevel.SAFE: {
        "icon": "🟢",
        "label": "SAFE",
        "color": "#34d399",   # green
        "confirm": False,
    },
    SecurityLevel.MEDIUM: {
        "icon": "🟡",
        "label": "MEDIUM",
        "color": "#fbbf24",   # yellow
        "confirm": False,
    },
    SecurityLevel.SENSITIVE: {
        "icon": "🟠",
        "label": "SENSITIVE",
        "color": "#f97316",   # orange
        "confirm": True,
    },
    SecurityLevel.CRITICAL: {
        "icon": "🔴",
        "label": "CRITICAL",
        "color": "#ef4444",   # red
        "confirm": True,
    },
}

# Destructive command keywords that escalate run_command to SENSITIVE
DESTRUCTIVE_KEYWORDS = {
    "del ", "rm ", "rmdir", "remove-item", "format ", "shutdown",
    "restart", "taskkill", "reg delete", "reg add", "diskpart",
    "cipher /w", "sfc ", "dism", "bcdedit", "wmic os",
}


class ActionExecutor:
    """
    Central gateway for all tool execution.
    Shows live action panels, checks permissions, and logs everything.
    """

    def __init__(self, ui=None):
        self._ui = ui
        self._action_count = 0
        self._denied_count = 0
        self._total_time_ms = 0.0

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_func: Callable,
        security_level: SecurityLevel = SecurityLevel.SAFE,
        timeout: float = 120.0,
    ) -> str:
        """
        Execute a tool with visibility, security checks, and logging.

        Args:
            tool_name: Name of the tool being called.
            arguments: Arguments to pass to the tool function.
            tool_func: The actual function to call.
            security_level: SecurityLevel for this action.
            timeout: Max execution time in seconds.

        Returns:
            String result from the tool, or denial/error message.
        """
        self._action_count += 1
        display = SECURITY_DISPLAY.get(security_level, SECURITY_DISPLAY[SecurityLevel.SAFE])

        # Dynamic escalation for run_command with destructive keywords
        if tool_name == "run_command" and security_level.value in ("safe", "medium"):
            cmd = str(arguments.get("command", "")).lower()
            if any(kw in cmd for kw in DESTRUCTIVE_KEYWORDS):
                security_level = SecurityLevel.SENSITIVE
                display = SECURITY_DISPLAY[SecurityLevel.SENSITIVE]

        # 1. Show action start panel
        if self._ui:
            self._ui.show_action_start(tool_name, arguments, security_level)

        # 2. Check if confirmation is required
        needs_confirm = display["confirm"]
        if needs_confirm:
            if self._ui:
                approved = self._ui.ask_permission(tool_name, arguments, security_level)
            else:
                # No UI available — deny by default for safety
                approved = False

            if not approved:
                self._denied_count += 1
                denial_msg = f"Action '{tool_name}' was denied by Dad."

                if self._ui:
                    self._ui.show_action_denied(tool_name, "Denied by user")

                tools_logger.info(json.dumps({
                    "action": "tool_denied",
                    "tool": tool_name,
                    "args": arguments,
                    "security_level": security_level.value,
                }, default=str))

                return denial_msg

        # 3. Execute the tool
        start = time.perf_counter()
        try:
            result = tool_func(**arguments)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._total_time_ms += elapsed_ms

            # Ensure result is a string
            if result is None:
                result = "Done."
            elif isinstance(result, (dict, list)):
                result = json.dumps(result, indent=2, default=str)
            else:
                result = str(result)

            # 4. Show action result
            if self._ui:
                self._ui.show_action_result(tool_name, result, elapsed_ms, success=True)

            # 5. Log
            tools_logger.info(json.dumps({
                "action": "tool_executed",
                "tool": tool_name,
                "args": arguments,
                "security_level": security_level.value,
                "duration_ms": round(elapsed_ms, 2),
                "result_length": len(result),
                "success": True,
            }, default=str))

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_msg = f"Tool '{tool_name}' failed: {e}"

            if self._ui:
                self._ui.show_action_result(tool_name, error_msg, elapsed_ms, success=False)

            tools_logger.info(json.dumps({
                "action": "tool_error",
                "tool": tool_name,
                "args": arguments,
                "security_level": security_level.value,
                "error": str(e),
                "duration_ms": round(elapsed_ms, 2),
            }, default=str))

            logger.error(f"ActionExecutor: {error_msg}")
            return error_msg

    @staticmethod
    def classify_command_risk(command: str) -> SecurityLevel:
        """
        Dynamically classify the security risk of a shell command.

        Returns SENSITIVE for destructive commands, MEDIUM otherwise.
        """
        cmd_lower = command.lower().strip()
        if any(kw in cmd_lower for kw in DESTRUCTIVE_KEYWORDS):
            return SecurityLevel.SENSITIVE
        return SecurityLevel.MEDIUM

    @property
    def stats(self) -> dict:
        """Return execution statistics."""
        return {
            "total_actions": self._action_count,
            "denied_actions": self._denied_count,
            "total_time_ms": round(self._total_time_ms, 2),
        }
