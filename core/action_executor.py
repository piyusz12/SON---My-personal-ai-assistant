# core/action_executor.py — Central Execution Gateway for SON
"""
All tool calls flow through ActionExecutor, which provides:
  1. Live action visibility — Rich panels showing what SON is doing
  2. Security level checking — SAFE/MEDIUM/SENSITIVE/CRITICAL classification
  3. Interactive confirmation — Dad approves dangerous actions before execution
  4. Argument validation — Registered Pydantic schemas enforced strictly
  5. Concurrency control & Deduplication — Serialization of Windows actions & deduplication
  6. Result validation & Secret redaction — Output bounding, credential scrubbing, untrusted wrapping
  7. Action logging — Every action logged with timing, status, and audit trail

Usage:
    executor = ActionExecutor(ui=terminal_ui)
    result = executor.execute("kill_process", {"name": "chrome"}, tool_func, security_level)
"""
import concurrent.futures
import inspect
import json
import logging
import threading
import time
from typing import Callable, Any, Optional

from pydantic import ValidationError

from core.config import Config, SecurityLevel
from core.security.policy import classify_risk, RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, canonical_args_hash, redact_secrets
from core.security.identity import identity_manager
from core.security.session_manager import session_manager
from core.security.schemas import ToolExecutionRequest, ToolExecutionResult
from core.security.result_validator import result_validator

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

# Non-thread-safe Windows desktop operations that must be serialized
WINDOWS_DESKTOP_TOOLS = {
    "open_application",
    "close_application",
    "set_volume",
    "set_brightness",
    "shutdown_pc",
    "restart_pc",
    "take_screenshot",
    "type_message",
    "minimize_window",
    "maximize_window",
    "snap_window",
}


def _filter_func_args(func: Callable, args: dict[str, Any]) -> dict[str, Any]:
    """Filter arguments to those accepted by the target callable when no **kwargs is present."""
    try:
        sig = inspect.signature(func)
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_var_kw:
            return args
        param_names = set(sig.parameters.keys())
        return {k: v for k, v in args.items() if k in param_names}
    except Exception:
        return args


class ActionExecutor:
    """
    Central gateway for all tool execution.
    Shows live action panels, checks permissions, validates schemas,
    enforces concurrency boundaries, validates results, and logs everything.
    """

    def __init__(self, ui=None, tracker=None):
        self._ui = ui
        self._tracker = tracker
        self._action_count = 0
        self._denied_count = 0
        self._total_time_ms = 0.0

        # Concurrency & deduplication state
        self._active_executions: set[tuple[str, str, str]] = set()
        self._exec_lock = threading.Lock()
        self._windows_lock = threading.RLock()
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=16,
            thread_name_prefix="action_exec",
        )

    def set_tracker(self, tracker):
        """Set the ThinkingTracker for real-time thinking visibility."""
        self._tracker = tracker

    def execute_typed(
        self,
        request: ToolExecutionRequest,
        tool_func: Optional[Callable] = None,
        context: Any | None = None,
        already_approved: bool = False,
    ) -> ToolExecutionResult:
        """
        Execute a tool request through the fully typed, zero-trust execution pipeline:
          1. SecurityContext & Identity validation
          2. ToolRegistry lookup & Pydantic schema argument validation
          3. Dynamic PolicyEngine evaluation
          4. Cryptographic approval verification & atomic consumption
          5. Concurrency deduplication & Windows operation serialization
          6. Bounded timeout execution
          7. Result validation, secret scrubbing, and delimiter wrapping
          8. Comprehensive security audit logging
        """
        start_time = time.perf_counter()
        tool_name = request.tool_name
        raw_args = dict(request.arguments or {})
        user_id = request.user_id
        session_id = request.session_id
        req_id = request.request_id

        # 1. Validate Context & Identity
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
                return ToolExecutionResult(
                    request_id=req_id,
                    tool_name=tool_name,
                    status="AUTHENTICATION_ERROR",
                    success=False,
                    result=msg,
                    error_code="UNAUTHENTICATED_CONTEXT",
                    execution_duration=0.0,
                    validation_status="REJECTED",
                )

            user_id = getattr(context, "user_id", user_id)
            session_id = getattr(context, "session_id", session_id)

        # Enforce valid user identity
        if not identity_manager.is_valid_user(user_id):
            self._denied_count += 1
            msg = f"Security Error: User '{user_id}' is not a recognized or active identity."
            audit_logger.log_event(
                event_type="IDENTITY_VALIDATION_FAILED",
                tool_name=tool_name,
                actor=user_id,
                session_id=session_id,
                status="BLOCKED",
                details={"reason": f"Unknown or inactive user '{user_id}'."},
            )
            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="AUTHENTICATION_ERROR",
                success=False,
                result=msg,
                error_code="UNKNOWN_USER_IDENTITY",
                execution_duration=0.0,
                validation_status="REJECTED",
            )

        # Validate session lifecycle
        valid_sess, sess_reason, _ = session_manager.validate_session(session_id, user_id)
        if not valid_sess:
            self._denied_count += 1
            msg = f"Security Error: Session validation failed: {sess_reason}"
            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="AUTHENTICATION_ERROR",
                success=False,
                result=msg,
                error_code="SESSION_VALIDATION_FAILED",
                execution_duration=0.0,
                validation_status="REJECTED",
            )

        # 2. Tool Lookup & Schema Validation
        from core.security.tool_registry import defensive_tool_registry
        reg_tool = defensive_tool_registry.get_tool(tool_name)

        if not reg_tool and tool_func is None:
            err = f"Security Error: Tool '{tool_name}' is not registered or supported."
            audit_logger.log_event(
                event_type="UNREGISTERED_TOOL_CALLED",
                tool_name=tool_name,
                arguments=raw_args,
                actor=user_id,
                session_id=session_id,
                status="REJECTED",
                details={"reason": "Unknown tool"},
            )
            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="REJECTED",
                success=False,
                result=err,
                error_code="UNREGISTERED_TOOL",
                execution_duration=0.0,
                validation_status="REJECTED",
            )

        handler = tool_func or (reg_tool.handler if reg_tool else None)
        validated_args = raw_args

        # Strict argument validation against Pydantic schema when registered
        if reg_tool and reg_tool.schema:
            try:
                validated_model = reg_tool.schema.model_validate(raw_args)
                validated_args = validated_model.model_dump()
            except ValidationError as val_err:
                err = f"Argument validation failed for tool '{tool_name}': {val_err}"
                audit_logger.log_event(
                    event_type="TOOL_VALIDATION_ERROR",
                    tool_name=tool_name,
                    arguments=raw_args,
                    actor=user_id,
                    session_id=session_id,
                    status="REJECTED",
                    details={"errors": val_err.errors()},
                )
                return ToolExecutionResult(
                    request_id=req_id,
                    tool_name=tool_name,
                    status="VALIDATION_ERROR",
                    success=False,
                    result=err,
                    error_code="INVALID_ARGUMENTS",
                    execution_duration=0.0,
                    validation_status="INVALID_INPUT",
                )

        # 3. Policy & Risk Classification
        risk = reg_tool.risk_tier if reg_tool else classify_risk(tool_name, validated_args)

        # When custom tool_func is passed directly (tests/callbacks), bypass strict registry allowlist in policy engine
        if reg_tool is None and tool_func is not None:
            needs_confirm = (risk == RiskTier.HIGH)
            policy_decision = None
        else:
            from core.security.policy_engine import policy_engine
            # If caller already provided an approval_id, policy_engine.evaluate_action will verify and consume it
            policy_decision = policy_engine.evaluate_action(
                tool_name=tool_name,
                arguments=validated_args,
                user_id=user_id,
                session_id=session_id,
                approval_id=request.approval_request_id,
            )
            needs_confirm = policy_decision.requires_approval

            if not policy_decision.allowed and not policy_decision.requires_approval and not already_approved:
                self._denied_count += 1
                msg = f"Security Error: Action '{tool_name}' denied by policy: {policy_decision.reason}"
                return ToolExecutionResult(
                    request_id=req_id,
                    tool_name=tool_name,
                    status="DENIED",
                    success=False,
                    result=msg,
                    error_code="POLICY_DENIAL",
                    execution_duration=0.0,
                    validation_status="POLICY_DENIED",
                )

        # 4. Human-in-the-Loop Approval Verification
        if needs_confirm and not already_approved:
            if request.approval_request_id:
                # If custom tool_func without policy_engine, verify and consume here
                if policy_decision is None:
                    valid, reason = approval_manager.verify_and_consume(
                        request.approval_request_id,
                        validated_args,
                        tool_name=tool_name,
                        session_id=session_id,
                        user_id=user_id,
                    )
                    if not valid:
                        self._denied_count += 1
                        msg = f"Security Error: Invalid or expired approval token for '{tool_name}' ({reason})."
                        return ToolExecutionResult(
                            request_id=req_id,
                            tool_name=tool_name,
                            status="DENIED",
                            success=False,
                            result=msg,
                            error_code="APPROVAL_VERIFICATION_FAILED",
                            execution_duration=0.0,
                            validation_status="DENIED",
                        )
                elif not policy_decision.allowed:
                    self._denied_count += 1
                    msg = f"Security Error: Invalid or expired approval token for '{tool_name}' ({policy_decision.reason})."
                    return ToolExecutionResult(
                        request_id=req_id,
                        tool_name=tool_name,
                        status="DENIED",
                        success=False,
                        result=msg,
                        error_code="APPROVAL_VERIFICATION_FAILED",
                        execution_duration=0.0,
                        validation_status="DENIED",
                    )
            else:
                # Create pending approval request and prompt interactive UI
                req = approval_manager.create_request(
                    tool_name=tool_name,
                    arguments=validated_args,
                    session_id=session_id,
                    user_id=user_id,
                    risk_level=risk,
                )
                approved = False
                if self._ui:
                    approved = self._ui.ask_permission(
                        tool_name,
                        redact_secrets(validated_args),
                        SecurityLevel.CRITICAL if risk == RiskTier.HIGH else SecurityLevel.SENSITIVE,
                    )
                    approval_manager.resolve_request(req.request_id, approved=approved, actor=user_id)

                if not approved:
                    self._denied_count += 1
                    denial_msg = f"Action '{tool_name}' was denied by Dad."
                    if self._ui:
                        self._ui.show_action_denied(tool_name, "Denied by user")
                    return ToolExecutionResult(
                        request_id=req_id,
                        tool_name=tool_name,
                        status="DENIED",
                        success=False,
                        result=denial_msg,
                        error_code="USER_DENIED",
                        execution_duration=0.0,
                        validation_status="DENIED",
                    )

                # Consume the verified ticket atomically
                valid, reason = approval_manager.verify_and_consume(
                    req.request_id,
                    validated_args,
                    tool_name=tool_name,
                    session_id=session_id,
                    user_id=user_id,
                )
                if not valid:
                    self._denied_count += 1
                    denial_msg = f"Security verification failed for '{tool_name}': {reason}"
                    return ToolExecutionResult(
                        request_id=req_id,
                        tool_name=tool_name,
                        status="DENIED",
                        success=False,
                        result=denial_msg,
                        error_code="APPROVAL_VERIFICATION_FAILED",
                        execution_duration=0.0,
                        validation_status="DENIED",
                    )

        # 5. Concurrency Deduplication Guard
        args_hash = canonical_args_hash(validated_args)
        exec_key = (session_id, tool_name, args_hash)

        with self._exec_lock:
            if exec_key in self._active_executions:
                msg = f"Concurrency Warning: Duplicate execution of '{tool_name}' already active in session '{session_id}'."
                logger.warning(msg)
                return ToolExecutionResult(
                    request_id=req_id,
                    tool_name=tool_name,
                    status="CONFLICT",
                    success=False,
                    result=msg,
                    error_code="DUPLICATE_EXECUTION_BLOCKED",
                    execution_duration=0.0,
                    validation_status="REJECTED",
                )
            self._active_executions.add(exec_key)

        # 6. Execute Approved Tool (with UI visibility & serialized Windows operations)
        self._action_count += 1
        if self._ui:
            sec_lvl = SecurityLevel.CRITICAL if risk == RiskTier.HIGH else SecurityLevel.SAFE
            self._ui.show_action_start(tool_name, redact_secrets(validated_args), sec_lvl)

        exec_start = time.perf_counter()
        try:
            call_args = _filter_func_args(handler, validated_args)
            is_windows_op = tool_name in WINDOWS_DESKTOP_TOOLS
            if is_windows_op:
                with self._windows_lock:
                    future = self._pool.submit(handler, **call_args)
                    raw_result = future.result(timeout=request.execution_timeout)
            else:
                future = self._pool.submit(handler, **call_args)
                raw_result = future.result(timeout=request.execution_timeout)

            exec_duration = time.perf_counter() - exec_start
            self._total_time_ms += exec_duration * 1000

            # 7. Result Validation & Sanitization
            wrap_untrusted = reg_tool.is_external_output if reg_tool else None
            validation = result_validator.validate_and_sanitize(
                tool_name=tool_name,
                raw_result=raw_result,
                session_id=session_id,
                user_id=user_id,
                wrap_untrusted=wrap_untrusted,
            )

            if self._ui:
                self._ui.show_action_result(tool_name, validation.sanitized_output, exec_duration * 1000, success=True)

            if self._tracker:
                preview = validation.sanitized_output[:60] + "..." if len(validation.sanitized_output) > 60 else validation.sanitized_output
                self._tracker.detail(f"{tool_name}: {preview}")

            # Structured Audit Logging
            audit_logger.log_event(
                event_type="ACTION_EXECUTED",
                tool_name=tool_name,
                arguments=validated_args,
                actor=user_id,
                session_id=session_id,
                risk_level=risk.value,
                approval_id=request.approval_request_id,
                status="SUCCESS",
                details={
                    "duration_ms": round(exec_duration * 1000, 2),
                    "truncated": validation.truncated,
                    "secrets_redacted": validation.contains_secrets_redacted,
                    "prompt_injection_flagged": validation.contains_prompt_injection,
                },
            )

            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="SUCCESS",
                success=True,
                result=validation.sanitized_output,
                execution_duration=round(exec_duration, 4),
                validation_status="VALIDATED",
                audit_reference=f"audit_{int(time.time()*1000)}",
            )

        except concurrent.futures.TimeoutError:
            exec_duration = time.perf_counter() - exec_start
            err_msg = f"Tool '{tool_name}' timed out after {request.execution_timeout}s."
            logger.error(err_msg)
            if self._ui:
                self._ui.show_action_result(tool_name, err_msg, exec_duration * 1000, success=False)
            audit_logger.log_event(
                event_type="TOOL_TIMEOUT_ERROR",
                tool_name=tool_name,
                actor=user_id,
                session_id=session_id,
                status="TIMEOUT",
                details={"timeout_seconds": request.execution_timeout},
            )
            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="TIMEOUT",
                success=False,
                result=err_msg,
                error_code="EXECUTION_TIMEOUT",
                execution_duration=round(exec_duration, 4),
                validation_status="TIMEOUT",
            )

        except Exception as e:
            exec_duration = time.perf_counter() - exec_start
            error_msg = f"Tool '{tool_name}' failed: {e}"
            logger.error(f"ActionExecutor: {error_msg}")
            if self._ui:
                self._ui.show_action_result(tool_name, error_msg, exec_duration * 1000, success=False)
            audit_logger.log_event(
                event_type="ACTION_FAILED",
                tool_name=tool_name,
                arguments=validated_args,
                actor=user_id,
                session_id=session_id,
                risk_level=risk.value,
                approval_id=request.approval_request_id,
                status="ERROR",
                details={"error": str(e), "duration_ms": round(exec_duration * 1000, 2)},
            )
            return ToolExecutionResult(
                request_id=req_id,
                tool_name=tool_name,
                status="ERROR",
                success=False,
                result=error_msg,
                error_code="TOOL_EXCEPTION",
                execution_duration=round(exec_duration, 4),
                validation_status="ERROR",
            )

        finally:
            with self._exec_lock:
                self._active_executions.discard(exec_key)

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_func: Callable | None = None,
        security_level: SecurityLevel = SecurityLevel.SAFE,
        timeout: float = 120.0,
        approval_id: str | None = None,
        already_approved: bool = False,
        context: Any | None = None,
    ) -> str:
        """
        Backward-compatible execution gateway delegating to the typed execution pipeline.
        Returns a normalized result string or denial/error message.
        """
        user_id = getattr(context, "user_id", "son_desktop_user") if context else "son_desktop_user"
        session_id = getattr(context, "session_id", "son_desktop_session") if context else "son_desktop_session"
        req_id = getattr(context, "request_id", None) or f"req_{int(time.time()*1000)}"

        # Ensure session registration
        if not session_manager.get_session(session_id):
            session_manager.register_session(session_id, user_id)

        # Dynamic risk tier classification for request
        risk = classify_risk(tool_name, arguments or {})

        req = ToolExecutionRequest(
            request_id=req_id,
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments or {},
            risk_level=risk.value,
            approval_request_id=approval_id,
            execution_timeout=float(timeout),
        )

        res = self.execute_typed(
            request=req,
            tool_func=tool_func,
            context=context,
            already_approved=already_approved,
        )

        return res.result

    @staticmethod
    def classify_command_risk(command: str) -> SecurityLevel:
        """Dynamically classify the security risk of a shell command."""
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
