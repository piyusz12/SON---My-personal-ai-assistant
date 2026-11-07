# agents/terminal_agent.py — Terminal & Shell Agent for SON V3
from typing import Any
from core.config import Config, SecurityLevel
from core.security.policy import classify_risk, RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, redact_secrets
from services.sandbox.e2b_service import sandbox_service, ExecutionResult


class TerminalAgent:
    """
    Executes terminal commands strictly inside isolated E2B microVM sandboxes
    with zero-trust policy checks, cryptographic approval gatekeeping, and structured audit logging.
    Arbitrary host command execution is permanently disabled.
    """

    def __init__(self, router=None, timeout: int = 60):
        self.router = router
        self.default_timeout = timeout

    def execute_command(
        self,
        command: str,
        cwd: str = None,
        approval_id: str | None = None,
        timeout: int | None = None,
    ) -> str:
        """
        Execute terminal command inside isolated E2B microVM.
        Enforces policy checks and human approval for high-risk operations.
        Never falls back to host execution.
        """
        cmd_raw = command.strip()
        if not cmd_raw:
            return "Empty command."

        risk = classify_risk("run_command", {"command": cmd_raw})

        if risk == RiskTier.HIGH:
            if not approval_id:
                req = approval_manager.create_request(
                    "run_command",
                    {"command": cmd_raw},
                    session_id="terminal_agent",
                )
                audit_logger.log_event(
                    event_type="COMMAND_APPROVAL_REQUIRED",
                    tool_name="terminal_agent.execute_command",
                    arguments={"command": cmd_raw},
                    risk_level="HIGH",
                    status="PENDING_APPROVAL",
                    approval_id=req.request_id,
                )
                return f"Command '{cmd_raw}' is HIGH RISK and requires approval (Request ID: {req.request_id})."

            valid, reason = approval_manager.verify_and_consume(
                approval_id,
                {"command": cmd_raw},
                tool_name="run_command",
                session_id="terminal_agent",
            )
            if not valid:
                return f"Security Error: {reason}"

        # Route exclusively through E2B Sandbox MicroVM
        exec_timeout = timeout or self.default_timeout
        result: ExecutionResult = sandbox_service.execute_terminal_command(
            command=cmd_raw,
            timeout=exec_timeout,
            session_id="terminal_agent",
        )

        audit_logger.log_event(
            event_type="SANDBOX_COMMAND_EXECUTED",
            tool_name="terminal_agent.execute_command",
            arguments={"command": cmd_raw},
            risk_level=risk.value,
            approval_id=approval_id,
            status="SUCCESS" if result.success else f"EXIT_{result.exit_code}",
            details={
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "execution_id": result.execution_id,
            },
        )

        if result.success:
            return result.stdout if result.stdout else f"Command completed in sandbox (Exit {result.exit_code})."
        else:
            err = result.stderr or result.error_message or "Unknown execution failure"
            return f"Sandbox Execution Error (Exit {result.exit_code}):\n{err}"
