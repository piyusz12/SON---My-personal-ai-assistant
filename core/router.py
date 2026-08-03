# core/router.py — Intent Router & Security Permission Dispatcher
"""
Parses user intent, checks security permission levels (Safe, Medium, Sensitive, Critical),
and dispatches requests to the appropriate Plugin or Brain LLM.
"""
from typing import Callable, Any
from core.config import Config, SecurityLevel


class IntentRouter:
    """
    Central dispatcher that evaluates action risks and routes to plugins or LLM.
    """

    def __init__(self, plugin_registry=None, state=None, ui_confirm_fn=None):
        self.plugins = plugin_registry
        self.state = state
        self.ui_confirm_fn = ui_confirm_fn  # Optional callback for asking user confirmation

    def check_permission(self, action_name: str, level: SecurityLevel, description: str = "") -> bool:
        """
        Check if an action is permitted under the current security policy.

        Returns:
            True if action can proceed, False if rejected by user.
        """
        if level == SecurityLevel.SAFE:
            return True

        if level == SecurityLevel.MEDIUM:
            # Log & execute
            if self.state:
                self.state.add_notification("Action Logged", f"Executed {action_name} ({description})", level="info")
            return True

        if level in (SecurityLevel.SENSITIVE, SecurityLevel.CRITICAL):
            if self.ui_confirm_fn:
                prompt_msg = f"Security Prompt [{level.value.upper()}]: Do you allow SON to '{action_name}' ({description})?"
                return self.ui_confirm_fn(prompt_msg, level)
            else:
                # Default CLI auto-confirm rule for sensitive if configured
                print(f"\n[SECURITY WARNING] Action '{action_name}' is {level.value.upper()}. Proceeding...")
                return True

        return True

    def dispatch_tool(self, tool_name: str, arguments: dict, tool_meta: dict) -> str:
        """
        Dispatch a tool call with security permission check.
        """
        level = tool_meta.get("security_level", SecurityLevel.SAFE)
        desc = tool_meta.get("description", "")

        if not self.check_permission(tool_name, level, desc):
            return f"Action '{tool_name}' cancelled by security policy."

        if self.plugins and self.plugins.has_tool(tool_name):
            return self.plugins.call(tool_name, arguments)

        return f"Error: Tool '{tool_name}' not found."
