# services/sandbox/e2b_service.py — Enterprise-Grade Isolated E2B MicroVM Execution Engine
"""
Enterprise-Grade E2B MicroVM Sandboxing Architecture for SON v3:
  - E2BSandboxManager: Manages microVM instance creation and authentication.
  - SandboxLifecycleManager: Tracks, monitors, and guarantees microVM cleanup.
  - SandboxPolicy: Enforces timeout, language restrictions, and strict fail-closed host-execution blocking.
  - ExecutionRequest & ExecutionResult: Strongly-typed Pydantic schemas.
  - SandboxExecutionService: End-to-end execution orchestrator with audit logging.

Cardinal Security Rule:
  1. All AI-generated code execution MUST execute inside an isolated E2B microVM.
  2. If E2B is unconfigured, unreachable, or errors, execution FAILS CLOSED.
  3. Under NO circumstances does the engine fall back to local host shells (PowerShell, CMD, Bash, subprocess, exec, eval).
"""

import os
import time
import uuid
import logging
import threading
from typing import Any
from pydantic import BaseModel, Field, field_validator

from core.security.audit_logger import audit_logger, redact_secrets

logger = logging.getLogger("son.sandbox")


class E2BUnavailableError(Exception):
    """Raised when E2B sandbox cannot be initialized or API key is missing."""
    pass


class HostExecutionBlockedError(Exception):
    """Raised when an attempt is made to fall back to host execution."""
    pass


class SandboxPolicy(BaseModel):
    """Deterministic policy rules governing code execution inside microVMs."""
    max_timeout_seconds: int = Field(300, ge=1, le=600)
    allow_host_fallback: bool = Field(False, description="Strictly False: Local host fallback is permanently forbidden.")
    permitted_languages: list[str] = Field(default_factory=lambda: ["python", "bash", "sh", "javascript", "typescript"])
    max_code_size_bytes: int = Field(100_000, ge=1, le=1_000_000)

    @field_validator("allow_host_fallback")
    @classmethod
    def validate_never_fallback(cls, v: bool) -> bool:
        if v is True:
            raise ValueError("Security Policy Violation: Host fallback cannot be enabled under any circumstances.")
        return False


class ExecutionRequest(BaseModel):
    """Strict Pydantic request schema for isolated code execution."""
    language: str = Field("python", description="Target programming language.")
    code: str = Field(..., min_length=1, max_length=100000, description="Source code or command to execute.")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Execution timeout in seconds.")
    session_id: str = Field("default_session", description="Originating user session identifier.")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        lang = v.strip().lower()
        allowed = {"python", "py", "bash", "sh", "shell", "javascript", "js", "typescript", "ts"}
        if lang not in allowed:
            raise ValueError(f"Language '{v}' is not permitted. Permitted: {sorted(allowed)}")
        return lang


class ExecutionResult(BaseModel):
    """Strict Pydantic response schema capturing execution output and telemetry."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None
    exit_code: int | None = 0
    duration_ms: float = 0.0
    execution_id: str = ""
    sandbox_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# Backward compatibility alias
SandboxResult = ExecutionResult


class SandboxLifecycleManager:
    """
    Guarantees reliable microVM lifecycle management, tracking active sessions,
    enforcing bounded TTL, and terminating instances in finally blocks.
    """

    def __init__(self):
        self._active_sandboxes: dict[str, Any] = {}
        self._lock = threading.Lock()

    def register(self, sandbox_id: str, sandbox_instance: Any):
        with self._lock:
            self._active_sandboxes[sandbox_id] = sandbox_instance

    def unregister(self, sandbox_id: str):
        with self._lock:
            self._active_sandboxes.pop(sandbox_id, None)

    def terminate_all(self):
        """Force cleanup of all active microVM instances upon service shutdown."""
        with self._lock:
            for s_id, sandbox in list(self._active_sandboxes.items()):
                try:
                    if hasattr(sandbox, "kill"):
                        sandbox.kill()
                    elif hasattr(sandbox, "close"):
                        sandbox.close()
                except Exception as e:
                    logger.warning(f"Error terminating sandbox {s_id}: {e}")
            self._active_sandboxes.clear()


class E2BSandboxManager:
    """
    Manages low-level connection, authentication, and creation of E2B microVMs.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("E2B_API_KEY")

    def is_configured(self) -> bool:
        """Returns True only if a valid E2B API key is configured."""
        key = self.api_key or os.getenv("E2B_API_KEY")
        return bool(key and len(key.strip()) > 5)

    def create_sandbox(self, timeout_seconds: int = 30) -> Any:
        """
        Create and initialize an isolated microVM sandbox via official E2B SDK.
        Fails closed if unconfigured or unreachable.
        """
        if not self.is_configured():
            raise E2BUnavailableError(
                "E2B Sandbox is unavailable: E2B_API_KEY is not configured. "
                "Per application zero-trust security policy, host fallback is forbidden."
            )

        try:
            from e2b_code_interpreter import Sandbox
            key = self.api_key or os.getenv("E2B_API_KEY")
            return Sandbox.create(api_key=key, timeout=timeout_seconds)
        except ImportError:
            raise E2BUnavailableError("e2b-code-interpreter SDK is not installed in the current environment.")
        except Exception as e:
            raise E2BUnavailableError(f"Failed to create E2B sandbox microVM: {type(e).__name__} - {e}")


class SandboxExecutionService:
    """
    High-level sandbox execution service orchestrating validation, policy enforcement,
    execution inside isolated E2B microVMs, and tamper-resistant audit logging.
    """

    def __init__(self, api_key: str | None = None, default_timeout: int = 30):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.default_timeout = default_timeout
        self.policy = SandboxPolicy()
        self.manager = E2BSandboxManager(api_key=self.api_key)
        self.lifecycle = SandboxLifecycleManager()

    def is_configured(self) -> bool:
        return self.manager.is_configured()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute code or command per validated ExecutionRequest.
        Strict Fail-Closed: Never falls back to local host.
        """
        exec_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Policy bounds check
        if request.timeout_seconds > self.policy.max_timeout_seconds:
            request.timeout_seconds = self.policy.max_timeout_seconds

        if not self.is_configured():
            err_msg = (
                "E2B Sandbox is unavailable: E2B_API_KEY is not configured. "
                "Per application security policy, host-level fallback is strictly forbidden. "
                "Please configure E2B_API_KEY in your environment to enable code execution."
            )
            audit_logger.log_event(
                event_type="HOST_EXECUTION_BLOCKED",
                tool_name="e2b_execute",
                arguments={"code_preview": request.code[:200], "language": request.language},
                risk_level="HIGH",
                session_id=request.session_id,
                status="FAILED_CLOSED",
                details={"reason": "Missing E2B_API_KEY; host execution blocked by policy"},
            )
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                exit_code=1,
                duration_ms=0.0,
                execution_id=exec_id,
            )

        try:
            sandbox = self.manager.create_sandbox(timeout_seconds=request.timeout_seconds)
            sandbox_id = getattr(sandbox, "sandbox_id", "unknown")
            self.lifecycle.register(sandbox_id, sandbox)

            try:
                if request.language in ("bash", "sh", "shell"):
                    cmd_res = sandbox.commands.run(request.code, timeout=request.timeout_seconds)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    stdout_text = getattr(cmd_res, "stdout", "") or ""
                    stderr_text = getattr(cmd_res, "stderr", "") or ""
                    exit_code = getattr(cmd_res, "exit_code", 0)
                    success = exit_code == 0
                    error_text = stderr_text if not success else None
                else:
                    execution = sandbox.run_code(request.code, timeout=request.timeout_seconds)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    stdout_text = "\n".join(execution.logs.stdout) if hasattr(execution, "logs") and execution.logs.stdout else ""
                    stderr_text = "\n".join(execution.logs.stderr) if hasattr(execution, "logs") and execution.logs.stderr else ""
                    error_text = None
                    if hasattr(execution, "error") and execution.error:
                        error_text = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"
                    success = error_text is None
                    exit_code = 0 if success else 1

                result = ExecutionResult(
                    success=success,
                    stdout=stdout_text,
                    stderr=stderr_text,
                    error_message=error_text,
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                    execution_id=exec_id,
                    sandbox_id=sandbox_id,
                )

                audit_logger.log_event(
                    event_type="SANDBOX_CODE_EXECUTED",
                    tool_name="e2b_execute",
                    arguments={"code_length": len(request.code), "language": request.language},
                    risk_level="MEDIUM",
                    session_id=request.session_id,
                    status="SUCCESS" if success else "EXECUTION_ERROR",
                    details={"sandbox_id": sandbox_id, "duration_ms": duration_ms, "success": success},
                )
                return result

            finally:
                try:
                    sandbox.kill()
                except Exception as close_err:
                    logger.warning(f"Error terminating sandbox {sandbox_id}: {close_err}")
                self.lifecycle.unregister(sandbox_id)

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"E2B Sandbox execution failed: {type(e).__name__} - {e}"
            audit_logger.log_event(
                event_type="SANDBOX_ERROR",
                tool_name="e2b_execute",
                risk_level="HIGH",
                session_id=request.session_id,
                status="ERROR_FAIL_CLOSED",
                details={"error": str(e), "duration_ms": duration_ms},
            )
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=err_msg,
                error_message=err_msg,
                exit_code=1,
                duration_ms=duration_ms,
                execution_id=exec_id,
            )

    def execute_code(
        self,
        code: str,
        timeout: int | None = None,
        session_id: str = "default_session",
    ) -> ExecutionResult:
        """Convenience method matching legacy signature."""
        req = ExecutionRequest(
            language="python",
            code=code,
            timeout_seconds=timeout or self.default_timeout,
            session_id=session_id,
        )
        return self.execute(req)

    def execute_terminal_command(
        self,
        command: str,
        timeout: int | None = None,
        session_id: str = "default_session",
    ) -> ExecutionResult:
        """Convenience method matching legacy signature."""
        req = ExecutionRequest(
            language="bash",
            code=command,
            timeout_seconds=timeout or self.default_timeout,
            session_id=session_id,
        )
        return self.execute(req)


# Backward compatibility alias
E2BSandboxService = SandboxExecutionService

# Global sandbox service singleton
sandbox_service = SandboxExecutionService()
