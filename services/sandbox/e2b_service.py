# services/sandbox/e2b_service.py — Isolated E2B MicroVM Execution Engine
"""
Official E2B SDK execution service providing isolated microVM sandboxing for code.
Enforces the cardinal rule:
  - All AI-generated code execution MUST execute inside an isolated E2B microVM.
  - If E2B is unavailable or unconfigured, execution FAILS CLOSED.
  - Under NO circumstances does the service fall back to local host shells,
    CMD, PowerShell, or subprocesses.
"""

import os
import time
import uuid
import logging
from dataclasses import dataclass
from typing import Any

from core.security.audit_logger import audit_logger, redact_secrets

logger = logging.getLogger("son.sandbox")


class E2BUnavailableError(Exception):
    """Raised when E2B sandbox cannot be initialized or API key is missing."""
    pass


class HostExecutionBlockedError(Exception):
    """Raised when an attempt is made to fall back to host execution."""
    pass


@dataclass
class SandboxResult:
    """Result of code or command execution within E2B microVM."""
    success: bool
    stdout: str
    stderr: str
    error_message: str | None = None
    exit_code: int | None = None
    duration_ms: float = 0.0
    execution_id: str = ""
    sandbox_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_message": self.error_message,
            "exit_code": self.exit_code,
            "duration_ms": round(self.duration_ms, 2),
            "execution_id": self.execution_id,
            "sandbox_id": self.sandbox_id,
        }


class E2BSandboxService:
    """
    Dedicated E2B sandbox service managing isolated microVMs for code execution.
    """

    def __init__(self, api_key: str | None = None, default_timeout: int = 30):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.default_timeout = default_timeout

    def is_configured(self) -> bool:
        """Check if an E2B API key is configured."""
        key = self.api_key or os.getenv("E2B_API_KEY")
        return bool(key and len(key.strip()) > 5)

    def execute_code(
        self,
        code: str,
        timeout: int | None = None,
        session_id: str = "default_session",
    ) -> SandboxResult:
        """
        Execute arbitrary Python code inside an isolated E2B microVM.

        Strict Fail-Closed Enforcement:
        - If E2B is unconfigured or encounters an error, execution stops immediately.
        - Host fallback is explicitly forbidden and blocked.
        """
        exec_id = str(uuid.uuid4())
        effective_timeout = timeout or self.default_timeout
        start_time = time.perf_counter()

        if not self.is_configured():
            err_msg = (
                "E2B Sandbox is unavailable: E2B_API_KEY is not configured. "
                "Per application security policy, host-level fallback is strictly forbidden. "
                "Please configure E2B_API_KEY in your environment to enable code execution."
            )
            audit_logger.log_event(
                event_type="HOST_EXECUTION_BLOCKED",
                tool_name="e2b_execute_code",
                arguments={"code_preview": code[:200]},
                risk_level="HIGH",
                session_id=session_id,
                status="FAILED_CLOSED",
                details={"reason": "Missing E2B_API_KEY; host execution blocked by policy"},
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                execution_id=exec_id,
            )

        try:
            from e2b_code_interpreter import Sandbox

            api_key = self.api_key or os.getenv("E2B_API_KEY")
            sandbox = Sandbox.create(api_key=api_key, timeout=effective_timeout)
            sandbox_id = getattr(sandbox, "sandbox_id", "unknown")

            try:
                execution = sandbox.run_code(code, timeout=effective_timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000

                stdout_text = ""
                stderr_text = ""
                error_text = None

                if hasattr(execution, "logs"):
                    stdout_text = "\n".join(execution.logs.stdout) if execution.logs.stdout else ""
                    stderr_text = "\n".join(execution.logs.stderr) if execution.logs.stderr else ""

                if hasattr(execution, "error") and execution.error:
                    error_text = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"

                success = error_text is None

                result = SandboxResult(
                    success=success,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    error_message=error_text,
                    exit_code=0 if success else 1,
                    duration_ms=duration_ms,
                    execution_id=exec_id,
                    sandbox_id=sandbox_id,
                )

                audit_logger.log_event(
                    event_type="SANDBOX_CODE_EXECUTED",
                    tool_name="e2b_execute_code",
                    arguments={"code_length": len(code)},
                    risk_level="MEDIUM",
                    session_id=session_id,
                    status="SUCCESS" if success else "EXECUTION_ERROR",
                    details={
                        "sandbox_id": sandbox_id,
                        "duration_ms": duration_ms,
                        "success": success,
                    },
                )
                return result

            finally:
                try:
                    sandbox.kill()
                except Exception as close_err:
                    logger.warning(f"Error terminating sandbox {sandbox_id}: {close_err}")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"E2B Sandbox execution failed: {type(e).__name__} - {e}"
            audit_logger.log_event(
                event_type="SANDBOX_ERROR",
                tool_name="e2b_execute_code",
                risk_level="HIGH",
                session_id=session_id,
                status="ERROR_FAIL_CLOSED",
                details={"error": str(e), "duration_ms": duration_ms},
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                duration_ms=duration_ms,
                execution_id=exec_id,
            )

    def execute_terminal_command(
        self,
        command: str,
        timeout: int | None = None,
        session_id: str = "default_session",
    ) -> SandboxResult:
        """
        Execute a shell command inside an isolated E2B microVM.
        Never executes on the local host machine.
        """
        exec_id = str(uuid.uuid4())
        effective_timeout = timeout or self.default_timeout
        start_time = time.perf_counter()

        if not self.is_configured():
            err_msg = (
                "E2B Sandbox is unavailable: E2B_API_KEY is not configured. "
                "Per application security policy, host-level fallback is strictly forbidden."
            )
            audit_logger.log_event(
                event_type="HOST_EXECUTION_BLOCKED",
                tool_name="e2b_execute_command",
                arguments={"command": command},
                risk_level="HIGH",
                session_id=session_id,
                status="FAILED_CLOSED",
                details={"reason": "Missing E2B_API_KEY; host command execution blocked by policy"},
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                execution_id=exec_id,
            )

        try:
            from e2b_code_interpreter import Sandbox

            api_key = self.api_key or os.getenv("E2B_API_KEY")
            sandbox = Sandbox.create(api_key=api_key, timeout=effective_timeout)
            sandbox_id = getattr(sandbox, "sandbox_id", "unknown")

            try:
                cmd_res = sandbox.commands.run(command, timeout=effective_timeout)
                duration_ms = (time.perf_counter() - start_time) * 1000

                stdout_text = getattr(cmd_res, "stdout", "") or ""
                stderr_text = getattr(cmd_res, "stderr", "") or ""
                exit_code = getattr(cmd_res, "exit_code", 0)

                success = exit_code == 0
                result = SandboxResult(
                    success=success,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                    execution_id=exec_id,
                    sandbox_id=sandbox_id,
                )

                audit_logger.log_event(
                    event_type="SANDBOX_COMMAND_EXECUTED",
                    tool_name="e2b_execute_command",
                    arguments={"command": command},
                    risk_level="MEDIUM",
                    session_id=session_id,
                    status="SUCCESS" if success else f"EXIT_{exit_code}",
                    details={"sandbox_id": sandbox_id, "duration_ms": duration_ms},
                )
                return result

            finally:
                try:
                    sandbox.kill()
                except Exception as close_err:
                    logger.warning(f"Error terminating sandbox {sandbox_id}: {close_err}")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"E2B Sandbox command execution failed: {type(e).__name__} - {e}"
            audit_logger.log_event(
                event_type="SANDBOX_COMMAND_ERROR",
                tool_name="e2b_execute_command",
                risk_level="HIGH",
                session_id=session_id,
                status="ERROR_FAIL_CLOSED",
                details={"error": str(e), "duration_ms": duration_ms},
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                duration_ms=duration_ms,
                execution_id=exec_id,
            )


# Global sandbox service singleton
sandbox_service = E2BSandboxService()

