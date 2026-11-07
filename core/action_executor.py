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
from core.security.policy import classify_risk, RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, redact_secrets
from core.security.sanitizer import wrap_untrusted_content

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

    def __init__(self, ui=None, tracker=None):
        self._ui = ui
        self._tracker = tracker
        self._action_count = 0
        self._denied_count = 0
        self._total_time_ms = 0.0

    def set_tracker(self, tracker):
        """Set the ThinkingTracker for real-time thinking visibility."""
        self._tracker = tracker

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_func: Callable,
        security_level: SecurityLevel = SecurityLevel.SAFE,
        timeout: float = 120.0,
        approval_id: str | None = None,
        already_approved: bool = False,
        context: Any | None = None,
    ) -> str:
        """
        Execute a tool with visibility, security checks, and logging.

        Args:
            tool_name: Name of the tool being called.
            arguments: Arguments to pass to the tool function.
            tool_func: The actual function to call.
            security_level: SecurityLevel for this action.
            timeout: Max execution time in seconds.
            approval_id: Optional pre-generated cryptographic approval request ID.
            already_approved: Whether human/policy approval was already verified upstream.
            context: SecurityContext carrying authenticated identity, session, and tracing data.

        Returns:
            String result from the tool, or denial/error message.
        """
        self._action_count += 1
        display = SECURITY_DISPLAY.get(security_level, SECURITY_DISPLAY[SecurityLevel.SAFE])

        # Enforce security context authentication if provided
        if context is not None:
            if not getattr(context, "is_authenticated", True):
                self._denied_count += 1
                msg = f"Security Error: Unauthenticated context rejected for tool '{tool_name}'."
                audit_logger.log_event(
                    event_type="UNAUTHENTICATED_EXECUTION_BLOCKED",
                    tool_name=tool_name,
                    actor=getattr(context, "user_id", "unauthenticated"),
                    session_id=getattr(context, "session_id", "unknown_session"),
                    status="BLOCKED",
                )
                if self._ui:
                    self._ui.show_action_denied(tool_name, "Unauthenticated context")
                return msg
            user_id = getattr(context, "user_id", "son_desktop_user")
            session_id = getattr(context, "session_id", "son_desktop_session")
        else:
            user_id = "son_desktop_user"
            session_id = "son_desktop_session"

        # Dynamic escalation based on security policy risk classification
        risk = classify_risk(tool_name, arguments)
        if risk == RiskTier.HIGH and security_level.value in ("safe", "medium"):
            security_level = SecurityLevel.CRITICAL
            display = SECURITY_DISPLAY[SecurityLevel.CRITICAL]
        elif tool_name == "run_command" and security_level.value in ("safe", "medium"):
            cmd = str(arguments.get("command", "")).lower()
            if any(kw in cmd for kw in DESTRUCTIVE_KEYWORDS):
                security_level = SecurityLevel.SENSITIVE
                display = SECURITY_DISPLAY[SecurityLevel.SENSITIVE]

        # 1. Show action start panel
        if self._ui:
            self._ui.show_action_start(tool_name, redact_secrets(arguments), security_level)

        # 2. Check if confirmation is required
        needs_confirm = display["confirm"] or (risk == RiskTier.HIGH)
        approval_req = None
        if needs_confirm and not already_approved:
            if approval_id:
                valid, reason = approval_manager.verify_and_consume(
                    approval_id,
                    arguments,
                    tool_name=tool_name,
                    session_id=session_id,
                    user_id=user_id,
                )
                if not valid:
                    self._denied_count += 1
                    denial_msg = f"Security Error: Invalid or expired approval token for '{tool_name}' ({reason})."
                    if self._ui:
                        self._ui.show_action_denied(tool_name, reason)
                    return denial_msg
                approved = True
            else:
                approval_req = approval_manager.create_request(
                    tool_name=tool_name,
                    arguments=arguments,
                    session_id=session_id,
                    user_id=user_id,
                    risk_level=risk,
                )

                if self._ui:
                    approved = self._ui.ask_permission(tool_name, redact_secrets(arguments), security_level)
                else:
                    # No UI available — deny by default for safety
                    approved = False

                approval_manager.resolve_request(approval_req.request_id, approved=approved, actor="user")

            if not approved:
                self._denied_count += 1
                denial_msg = f"Action '{tool_name}' was denied by Dad."

                if self._ui:
                    self._ui.show_action_denied(tool_name, "Denied by user")

                tools_logger.info(json.dumps({
                    "action": "tool_denied",
                    "tool": tool_name,
                    "args": redact_secrets(arguments),
                    "security_level": security_level.value,
                    "approval_id": approval_req.request_id if approval_req else approval_id,
                    "user_id": user_id,
                    "session_id": session_id,
                }, default=str))

                return denial_msg

            # Verify and consume the approval ticket (checks argument integrity & prevents replay)
            valid, reason = approval_manager.verify_and_consume(
                approval_req.request_id,
                arguments,
                tool_name=tool_name,
                session_id=session_id,
                user_id=user_id,
            )
            if not valid:
                self._denied_count += 1
                denial_msg = f"Security verification failed for '{tool_name}': {reason}"
                if self._ui:
                    self._ui.show_action_denied(tool_name, reason)
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

            # Untrusted content delimiter wrapping for external sources
            if tool_name in ("read_file", "read_webpage", "web_search", "news", "summarize_url"):
                result = wrap_untrusted_content(
                    content=result,
                    source=f"tool:{tool_name}",
                    source_type="external_resource",
                )

            # 4. Show action result
            if self._ui:
                self._ui.show_action_result(tool_name, result, elapsed_ms, success=True)

            # 4b. Emit thinking detail for tool result
            if self._tracker:
                preview = result[:60] + "..." if len(result) > 60 else result
                self._tracker.detail(f"{tool_name}: {preview}")

            # 5. Log securely with secret redaction
            tools_logger.info(json.dumps({
                "action": "tool_executed",
                "tool": tool_name,
                "args": redact_secrets(arguments),
                "security_level": security_level.value,
                "duration_ms": round(elapsed_ms, 2),
                "result_length": len(result),
                "user_id": user_id,
                "session_id": session_id,
                "success": True,
            }, default=str))

            audit_logger.log_event(
                event_type="ACTION_EXECUTED",
                tool_name=tool_name,
                arguments=arguments,
                actor=user_id,
                session_id=session_id,
                risk_level=security_level.value,
                approval_id=approval_req.request_id if approval_req else approval_id,
                status="SUCCESS",
                details={"duration_ms": round(elapsed_ms, 2)},
            )

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_msg = f"Tool '{tool_name}' failed: {e}"

            if self._ui:
                self._ui.show_action_result(tool_name, error_msg, elapsed_ms, success=False)

            safe_args = redact_secrets(arguments)
            tools_logger.info(json.dumps({
                "action": "tool_error",
                "tool": tool_name,
                "args": safe_args,
                "security_level": security_level.value,
                "error": str(e),
                "duration_ms": round(elapsed_ms, 2),
                "user_id": user_id,
                "session_id": session_id,
            }, default=str))

            audit_logger.log_event(
                event_type="ACTION_FAILED",
                tool_name=tool_name,
                arguments=arguments,
                actor=user_id,
                session_id=session_id,
                risk_level=security_level.value,
                approval_id=approval_req.request_id if approval_req else approval_id,
                status="ERROR",
                details={"error": str(e), "duration_ms": round(elapsed_ms, 2)},
            )

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
