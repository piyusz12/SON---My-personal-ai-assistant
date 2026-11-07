from core.config import SecurityLevel
from core.security.audit_logger import audit_logger


class SecurityRouter:
    """
    Central dispatcher that evaluates action risks and routes to plugins or LLM.
    Enforces strict fail-closed authorization.
    """

    def __init__(self, plugin_registry=None, state=None, ui_confirm_fn=None):
        self.plugins = plugin_registry
        self.state = state
        self.ui_confirm_fn = ui_confirm_fn  # Optional callback for asking user confirmation

    def check_permission(self, action_name: str, level: SecurityLevel, description: str = "") -> bool:
        """
        Check if an action is permitted under the current security policy.
        Enforces strict fail-closed behavior: sensitive/critical actions without
        interactive UI confirmation are DENIED and audited.

        Returns:
            True if action can proceed, False if rejected by user or denied by policy.
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
                approved = self.ui_confirm_fn(prompt_msg, level)
                if approved:
                    audit_logger.log_event(
                        event_type="PERMISSION_GRANTED_UI",
                        tool_name=action_name,
                        risk_level=level.value,
                        status="APPROVED",
                        details={"description": description},
                    )
                    return True
                else:
                    audit_logger.log_event(
                        event_type="PERMISSION_DENIED_USER",
                        tool_name=action_name,
                        risk_level=level.value,
                        status="DENIED",
                        details={"description": description},
                    )
                    return False
            else:
                # Fail-closed: Deny sensitive/critical actions when no interactive UI callback exists
                audit_logger.log_event(
                    event_type="PERMISSION_DENIED_FAIL_CLOSED",
                    tool_name=action_name,
                    risk_level=level.value,
                    status="DENIED_NO_UI",
                    details={
                        "reason": f"Sensitive action '{action_name}' denied because no interactive UI confirmation callback is attached.",
                        "description": description,
                    },
                )
                print(f"\n[SECURITY BLOCKED] Action '{action_name}' is {level.value.upper()} and denied by fail-closed policy (no UI confirmation available).")
                return False

        return True

    def dispatch_tool(self, tool_name: str, arguments: dict, tool_meta: dict) -> str:
        """
        Dispatch a tool call with security permission check.
        """
        level = tool_meta.get("security_level", SecurityLevel.SAFE)
        desc = tool_meta.get("description", "")

        if not self.check_permission(tool_name, level, desc):
            return f"Security Error: Action '{tool_name}' [{level.value.upper()}] denied by fail-closed policy (requires explicit user authorization)."

        if self.plugins and self.plugins.has_tool(tool_name):
            return self.plugins.call(tool_name, arguments)

        return f"Error: Tool '{tool_name}' not found."


# Backward compatibility alias
IntentRouter = SecurityRouter
