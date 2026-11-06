# agents/terminal_agent.py — Terminal & Shell Agent for SON V3
import subprocess
from core.config import Config, SecurityLevel
from core.security.policy import classify_risk, RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, redact_secrets


class TerminalAgent:
    """
    Executes terminal commands with policy checks, approval gatekeeping, and audit logging.
    """

    def __init__(self, router=None):
        self.router = router

    def execute_command(self, command: str, cwd: str = None, approval_id: str | None = None) -> str:
        """Run a terminal command with security policy checks and cryptographic approval."""
        cmd_raw = command.strip()
        risk = classify_risk("run_command", {"command": cmd_raw})

        if risk == RiskTier.HIGH:
            if not approval_id:
                req = approval_manager.create_request("run_command", {"command": cmd_raw})
                audit_logger.log_event(
                    event_type="HOST_COMMAND_APPROVAL_REQUIRED",
                    tool_name="terminal_agent.execute_command",
                    arguments={"command": cmd_raw},
                    risk_level="HIGH",
                    status="PENDING_APPROVAL",
                    approval_id=req.request_id,
                )
                return f"Command '{cmd_raw}' is HIGH RISK and requires approval (Request ID: {req.request_id})."

            valid, reason = approval_manager.verify_and_consume(approval_id, {"command": cmd_raw})
            if not valid:
                return f"Security Error: {reason}"

        # Legacy whitelist compatibility check
        whitelist = getattr(Config, "TERMINAL_COMMAND_WHITELIST", None)
        if whitelist:
            cmd_lower = cmd_raw.lower()
            allowed = any(cmd_lower.startswith(w.lower()) for w in whitelist)
            level = SecurityLevel.SAFE if allowed else SecurityLevel.SENSITIVE
            if self.router and not self.router.check_permission("terminal_command", level, cmd_raw):
                return f"Command '{command}' blocked by security policy."

        try:
            res = subprocess.run(
                cmd_raw, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
            )
            out = res.stdout.strip() or res.stderr.strip()
            audit_logger.log_event(
                event_type="HOST_COMMAND_EXECUTED",
                tool_name="terminal_agent.execute_command",
                arguments={"command": cmd_raw},
                risk_level=risk.value,
                approval_id=approval_id,
                status="SUCCESS" if res.returncode == 0 else f"EXIT_{res.returncode}",
            )
            return out if out else f"Command '{command}' executed successfully."
        except subprocess.TimeoutExpired:
            return f"Command '{command}' timed out."
        except Exception as e:
            return f"Command execution error: {e}"
