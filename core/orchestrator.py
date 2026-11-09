# core/orchestrator.py — Centralized SON Orchestrator Engine
"""
Centralized Orchestration Engine for SON V3:
Enforces the mandatory execution pipeline:
  USER INTERFACE (Voice, CLI, Desktop UI / HUD, WhatsApp, Automation)
  ↓
  SON ORCHESTRATOR
  ↓
  DEFENSIVE PYDANTICAI AGENT
  ↓
  SECURITY POLICY ENGINE
  ↓
  ACTION EXECUTOR
  ↓
  TOOL REGISTRY
  ↓
  APPROVED TOOL IMPLEMENTATION
  ↓
  RESULT VALIDATION AND AUDIT LOGGING

Zero-Trust Guarantees:
  1. No interface or legacy component can execute system actions directly.
  2. Strict SecurityContext verification (user_id, session_id, authentication).
  3. Prompt injection detection and untrusted input gating.
  4. Cryptographic approval tokens bound to action, user, session, and arguments.
  5. E2B isolated sandbox for code/shell execution — fail-closed without host fallback.
  6. Comprehensive audit trail for every allowed, blocked, or failed action.
"""

from enum import Enum
import time
import logging
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import DeferredToolRequests

from core.config import Config, SecurityLevel
from core.action_executor import ActionExecutor
from core.security.context import (
    SecurityContext,
    RequestContext,
    SecurityContextError,
    create_trusted_context,
    create_request_context,
)
from core.security.policy import RiskTier, classify_risk
from core.security.policy_engine import SecurityPolicyEngine, policy_engine
from core.security.approval_manager import ApprovalManager, approval_manager, ApprovalStatus
from core.security.audit_logger import SecurityAuditLogger, audit_logger, redact_secrets
from core.security.sanitizer import detect_prompt_injection, wrap_untrusted_content
from core.security.tool_registry import DefensiveToolRegistry, defensive_tool_registry
from core.security.pydantic_agent import DefensivePydanticAgent
from core.security.identity import identity_manager
from core.security.session_manager import session_manager
from services.sandbox.e2b_service import sandbox_service

logger = Config.get_logger(__name__)


class OrchestrationStatus(str, Enum):
    SUCCESS = "success"
    PENDING_APPROVAL = "pending_approval"
    AWAITING_APPROVAL = "awaiting_approval"  # Backward compatibility alias
    DENIED = "denied"
    BLOCKED = "blocked"                      # Backward compatibility alias
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    TOOL_ERROR = "tool_error"
    SANDBOX_ERROR = "sandbox_error"
    INTERNAL_ERROR = "internal_error"
    ERROR = "error"                          # General error alias


class ActionResult(BaseModel):
    """Result of an action execution through the security pipeline."""
    success: bool
    output: str
    tool_name: str
    requires_approval: bool = False
    approval_id: Optional[str] = None
    risk_tier: str = "low"
    error: Optional[str] = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestratorResponse(BaseModel):
    """Structured response from the central orchestrator to the calling interface."""
    request_id: str
    status: OrchestrationStatus
    response_text: str = ""
    tool_results: list[ActionResult] = Field(default_factory=list)
    pending_approval: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)

    # Backward compatibility fields/properties with OrchestrationResult
    text: str = ""
    tool_name: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None
    approval_id: Optional[str] = None
    action_result: Optional[ActionResult] = None
    context: Optional[SecurityContext] = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync response_text and text
            if "response_text" in data and not data.get("text"):
                data["text"] = data["response_text"]
            elif "text" in data and not data.get("response_text"):
                data["response_text"] = data["text"]

            # Sync tool_results and action_result
            if "action_result" in data and data["action_result"] is not None and not data.get("tool_results"):
                data["tool_results"] = [data["action_result"]]
            elif "tool_results" in data and data["tool_results"] and not data.get("action_result"):
                data["action_result"] = data["tool_results"][0]

            # Sync pending_approval and approval_id
            if "approval_id" in data and data["approval_id"] and not data.get("pending_approval"):
                data["pending_approval"] = {
                    "approval_id": data["approval_id"],
                    "tool_name": data.get("tool_name"),
                    "status": "PENDING",
                }
            elif "pending_approval" in data and data["pending_approval"] and not data.get("approval_id"):
                if isinstance(data["pending_approval"], dict):
                    data["approval_id"] = data["pending_approval"].get("approval_id")

            # Sync execution_metadata and details
            if "details" in data and data["details"] and not data.get("execution_metadata"):
                data["execution_metadata"] = data["details"]
            elif "execution_metadata" in data and data["execution_metadata"] and not data.get("details"):
                data["details"] = data["execution_metadata"]
        return data


# Backward-compatible type alias
OrchestrationResult = OrchestratorResponse


class SonOrchestrator:
    """
    Central orchestration engine for SON V3.
    Directs all user inputs, policy decisions, approvals, and tool executions.
    """

    def __init__(
        self,
        pydantic_agent: Optional[DefensivePydanticAgent] = None,
        policy_engine_instance: Optional[SecurityPolicyEngine] = None,
        action_executor: Optional[ActionExecutor] = None,
        tool_registry: Optional[DefensiveToolRegistry] = None,
        approval_manager_instance: Optional[ApprovalManager] = None,
        command_handler: Any = None,
        ui: Any = None,
        sandbox: Any = None,
    ):
        self.action_executor = action_executor or ActionExecutor(ui=ui)
        self.pydantic_agent = pydantic_agent or DefensivePydanticAgent(executor=self.action_executor)
        self.policy_engine = policy_engine_instance or policy_engine
        self.tool_registry = tool_registry or defensive_tool_registry
        self.approval_manager = approval_manager_instance or approval_manager
        self.sandbox = sandbox or sandbox_service
        self.command_handler = command_handler
        self.ui = ui

        # Pending deferred agent turns: approval_id -> (run_result, context)
        self._deferred_runs: dict[str, tuple[Any, SecurityContext]] = {}

    def validate_context(self, context: Optional[SecurityContext]) -> SecurityContext:
        """
        Enforce valid, non-empty, authenticated SecurityContext.
        Rejects missing, unauthenticated, or malformed contexts fail-closed.
        """
        if context is None:
            audit_logger.log_event(
                event_type="MISSING_SECURITY_CONTEXT_BLOCKED",
                status="BLOCKED",
                details={"reason": "SecurityContext must be provided by application interface code."},
            )
            raise SecurityContextError("Missing SecurityContext. Direct execution without security context is rejected.")

        if not getattr(context, "is_authenticated", False):
            audit_logger.log_event(
                event_type="UNAUTHENTICATED_SECURITY_CONTEXT_BLOCKED",
                actor=getattr(context, "user_id", "unauthenticated"),
                session_id=getattr(context, "session_id", "unknown_session"),
                status="BLOCKED",
            )
            raise SecurityContextError(f"SecurityContext for user '{getattr(context, 'user_id', 'unknown')}' is not authenticated.")

        user_id = getattr(context, "user_id", "")
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            audit_logger.log_event(
                event_type="MISSING_USER_ID_BLOCKED",
                status="BLOCKED",
                details={"reason": "User ID must be non-empty."},
            )
            raise SecurityContextError("User ID must be a non-empty, authenticated identity string.")

        session_id = getattr(context, "session_id", "")
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            audit_logger.log_event(
                event_type="MISSING_SESSION_ID_BLOCKED",
                actor=user_id,
                status="BLOCKED",
                details={"reason": "Session ID must be non-empty."},
            )
            raise SecurityContextError("Session ID must be a non-empty, trusted session identifier.")

        # 1. Identity validation via centralized identity provider
        if not identity_manager.is_valid_user(user_id):
            audit_logger.log_event(
                event_type="IDENTITY_VALIDATION_FAILED",
                actor=user_id,
                session_id=session_id,
                status="BLOCKED",
                details={"reason": f"Unknown or inactive user '{user_id}'."},
            )
            raise SecurityContextError(f"User '{user_id}' is not authorized (not a recognized or active identity).")

        # 2. Session lifecycle validation (expiration, revocation, cross-user isolation)
        valid_sess, sess_reason, _ = session_manager.validate_session(session_id, user_id)
        if not valid_sess:
            raise SecurityContextError(f"Session validation failed: {sess_reason}")

        if not self.policy_engine.is_user_authorized(context.user_id, context.session_id):
            audit_logger.log_event(
                event_type="UNAUTHORIZED_USER_ORCHESTRATOR_BLOCKED",
                actor=context.user_id,
                session_id=context.session_id,
                status="BLOCKED",
            )
            raise SecurityContextError(f"User '{context.user_id}' is not authorized to perform actions.")

        return context

    def process_request(
        self,
        text: str,
        context: Optional[SecurityContext] = None,
    ) -> OrchestratorResponse:
        """
        Central processing pipeline for all user requests across all interfaces.

        Flow:
          1. SecurityContext validation
          2. Input normalization and prompt injection screening
          3. Fast-path deterministic command handling (via secure ActionExecutor)
          4. Defensive PydanticAI Agent execution
          5. Tool approval gating or execution
          6. Result formatting and audit logging
        """
        start_time = time.perf_counter()
        req_id = getattr(context, "request_id", None) or f"req_{int(time.time()*1000)}"

        # 1. Enforce trusted security context
        try:
            ctx = self.validate_context(context)
            req_id = ctx.request_id
        except SecurityContextError as sce:
            return OrchestratorResponse(
                request_id=req_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Security Error: {sce}",
                error=str(sce),
                execution_metadata={"error": str(sce), "failure_category": "security_violation"},
            )

        # 2. Input normalization & Prompt injection screening
        normalized_text = (text or "").strip()
        audit_logger.log_event(
            event_type="ORCHESTRATOR_REQUEST_RECEIVED",
            actor=ctx.user_id,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            status="PROCESSING",
            details={
                "interface_type": ctx.interface_type,
                "input_preview": normalized_text[:120],
            },
        )

        is_injection, injection_types = detect_prompt_injection(normalized_text)
        if is_injection:
            audit_logger.log_event(
                event_type="PROMPT_INJECTION_FLAGGED",
                actor=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                status="FLAGGED",
                details={"injection_types": injection_types, "input_preview": normalized_text[:150]},
            )
            logger.warning(f"Prompt injection patterns detected from {ctx.user_id}: {injection_types}")

        # 3. Deterministic Command Handling (Pattern-matched commands route through orchestrator)
        if self.command_handler and hasattr(self.command_handler, "handle"):
            handled, cmd_result = self.command_handler.handle(normalized_text)
            if handled:
                duration_ms = (time.perf_counter() - start_time) * 1000
                audit_logger.log_event(
                    event_type="COMMAND_HANDLER_EXECUTED",
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    request_id=ctx.request_id,
                    status="SUCCESS",
                    details={"text": normalized_text[:80], "duration_ms": duration_ms},
                )
                return OrchestratorResponse(
                    request_id=ctx.request_id,
                    status=OrchestrationStatus.SUCCESS,
                    response_text=cmd_result or "Command executed.",
                    context=ctx,
                    execution_metadata={"duration_ms": duration_ms, "handler": "command_handler"},
                )

        # 4. Defensive PydanticAI Agent Execution
        try:
            run_result = self.pydantic_agent.run(
                user_prompt=normalized_text,
                session_id=ctx.session_id,
                context=ctx,
            )
        except SecurityContextError as sce:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Security Error: {sce}",
                error=str(sce),
                context=ctx,
                execution_metadata={"duration_ms": duration_ms, "failure_category": "security_violation"},
            )
        except TimeoutError as te:
            duration_ms = (time.perf_counter() - start_time) * 1000
            audit_logger.log_event(
                event_type="AGENT_TIMEOUT_ERROR",
                actor=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                status="ERROR",
                details={"error": str(te)},
            )
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.ERROR,
                response_text="Agent execution timed out. Please try again.",
                error="Agent execution timed out",
                context=ctx,
                execution_metadata={"duration_ms": duration_ms, "failure_category": "agent_timeout"},
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(e)
            logger.error(f"Error during PydanticAI agent turn: {e}", exc_info=True)
            category = "model_unavailable" if any(w in err_str.lower() for w in ("connection", "unavailable", "offline", "unreachable")) else "agent_error"
            audit_logger.log_event(
                event_type="AGENT_EXECUTION_ERROR",
                actor=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                status="ERROR",
                details={"error": err_str, "category": category},
            )
            safe_msg = "Model service is currently unavailable. Please verify connection and model status." if category == "model_unavailable" else f"An error occurred while processing your request: {err_str}"
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.ERROR,
                response_text=safe_msg,
                error=err_str,
                context=ctx,
                execution_metadata={"duration_ms": duration_ms, "failure_category": category},
            )

        # 5. Deferred Approval Handling
        if isinstance(run_result.output, DeferredToolRequests):
            deferred: DeferredToolRequests = run_result.output
            if deferred.approvals:
                first_approval = deferred.approvals[0]
                call_id = first_approval.tool_call_id
                req_id_approval = self.pydantic_agent._call_to_request.get(call_id)
                tool_name = first_approval.tool_name
                args = first_approval.args if isinstance(first_approval.args, dict) else {}

                if req_id_approval:
                    self._deferred_runs[req_id_approval] = (run_result, ctx)

                approval_prompt = (
                    f"Action '{tool_name}' requires Dad's explicit authorization. "
                    f"Arguments: {redact_secrets(args)}. Approve? (ID: {req_id_approval})"
                )

                audit_logger.log_event(
                    event_type="ORCHESTRATOR_AWAITING_APPROVAL",
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    request_id=ctx.request_id,
                    tool_name=tool_name,
                    approval_id=req_id_approval,
                    status="AWAITING_APPROVAL",
                )

                duration_ms = (time.perf_counter() - start_time) * 1000
                return OrchestratorResponse(
                    request_id=ctx.request_id,
                    status=OrchestrationStatus.AWAITING_APPROVAL,
                    response_text=approval_prompt,
                    tool_name=tool_name,
                    arguments=args,
                    approval_id=req_id_approval,
                    pending_approval={
                        "approval_id": req_id_approval,
                        "tool_name": tool_name,
                        "arguments": redact_secrets(args),
                        "status": ApprovalStatus.PENDING.value,
                    },
                    context=ctx,
                    execution_metadata={"duration_ms": duration_ms},
                )

        # 6. Completed Agent Turn
        duration_ms = (time.perf_counter() - start_time) * 1000
        final_text = str(run_result.output)
        audit_logger.log_event(
            event_type="ORCHESTRATOR_REQUEST_COMPLETED",
            actor=ctx.user_id,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            status="SUCCESS",
            details={"duration_ms": duration_ms},
        )
        return OrchestratorResponse(
            request_id=ctx.request_id,
            status=OrchestrationStatus.SUCCESS,
            response_text=final_text,
            context=ctx,
            execution_metadata={"duration_ms": duration_ms},
        )

    def execute_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: SecurityContext,
        approval_id: Optional[str] = None,
        tool_func: Optional[Callable] = None,
    ) -> ActionResult:
        """
        Execute an action explicitly through the mandatory security pipeline:
        PolicyEngine → Approval verification → ActionExecutor → DefensiveToolRegistry.

        All interface actions (direct CLI commands, WhatsApp, Automation) must call this method.
        """
        start_time = time.perf_counter()

        # 1. Enforce trusted security context
        try:
            ctx = self.validate_context(context)
        except SecurityContextError as sce:
            return ActionResult(
                success=False,
                output=f"Security Error: {sce}",
                tool_name=tool_name,
                risk_tier="high",
                error=str(sce),
                execution_metadata={"failure_category": "security_violation"},
            )

        # 2. Evaluate Policy
        decision = self.policy_engine.evaluate_action(
            tool_name=tool_name,
            arguments=arguments,
            user_id=ctx.user_id,
            session_id=ctx.session_id,
            approval_id=approval_id,
        )

        if not decision.allowed:
            if decision.requires_approval:
                return ActionResult(
                    success=False,
                    output=f"Action '{tool_name}' requires approval (human approval required). Request ID: {decision.approval_id}",
                    tool_name=tool_name,
                    requires_approval=True,
                    approval_id=decision.approval_id,
                    risk_tier=decision.risk_tier.value,
                    error="Approval required",
                )
            return ActionResult(
                success=False,
                output=f"Action '{tool_name}' denied by policy: {decision.reason}",
                tool_name=tool_name,
                requires_approval=False,
                risk_tier=decision.risk_tier.value,
                error=decision.reason,
            )

        # 3. Resolve Tool Implementation
        handler = tool_func
        sec_level = SecurityLevel.SAFE
        if handler is None:
            reg_tool = self.tool_registry.get_tool(tool_name)
            if not reg_tool:
                err_msg = f"Security Error: Tool '{tool_name}' is not in the DefensiveToolRegistry."
                audit_logger.log_event(
                    event_type="UNREGISTERED_TOOL_CALLED",
                    tool_name=tool_name,
                    arguments=arguments,
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    status="REJECTED",
                )
                return ActionResult(
                    success=False,
                    output=err_msg,
                    tool_name=tool_name,
                    risk_tier=decision.risk_tier.value,
                    error="Unregistered tool",
                )
            handler = reg_tool.handler
            if reg_tool.risk_tier == RiskTier.HIGH:
                sec_level = SecurityLevel.CRITICAL
            elif reg_tool.risk_tier == RiskTier.MEDIUM:
                sec_level = SecurityLevel.MEDIUM
        else:
            if decision.risk_tier == RiskTier.HIGH:
                sec_level = SecurityLevel.CRITICAL
            elif decision.risk_tier == RiskTier.MEDIUM:
                sec_level = SecurityLevel.MEDIUM

        # 4. Enforce Isolated E2B Sandbox for Code & Command Tools
        if tool_name in ("execute_python_code", "execute_sandbox_command"):
            try:
                # Execution for code/terminal MUST route through configured sandbox instance
                if tool_name == "execute_python_code":
                    code = arguments.get("code", "")
                    sb_res = self.sandbox.execute_python_code(
                        code=code,
                        user_id=ctx.user_id,
                        session_id=ctx.session_id,
                    )
                else:
                    command = arguments.get("command", "")
                    sb_res = self.sandbox.execute_terminal_command(
                        command=command,
                        user_id=ctx.user_id,
                        session_id=ctx.session_id,
                    )
                exec_result = sb_res.get("output", "") if isinstance(sb_res, dict) else str(sb_res)
            except Exception as e:
                logger.error(f"Sandbox execution failed for '{tool_name}': {e}", exc_info=True)
                audit_logger.log_event(
                    event_type="SANDBOX_EXECUTION_FAILED",
                    tool_name=tool_name,
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    status="ERROR",
                    details={"error": str(e)},
                )
                return ActionResult(
                    success=False,
                    output=f"Controlled Error: Sandbox execution failed: {e}",
                    tool_name=tool_name,
                    risk_tier=decision.risk_tier.value,
                    error="Sandbox execution failure — host fallback blocked",
                )
        else:
            # 5. Execute native / other tools through ActionExecutor
            try:
                from core.security.schemas import ToolExecutionRequest
                exec_req = ToolExecutionRequest(
                    request_id=ctx.request_id,
                    user_id=ctx.user_id,
                    session_id=ctx.session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=decision.risk_tier.value,
                    approval_request_id=approval_id or decision.approval_id,
                )
                typed_res = self.action_executor.execute_typed(
                    request=exec_req,
                    tool_func=handler,
                    context=ctx,
                    already_approved=decision.allowed,
                )
                exec_result = typed_res.result
            except Exception as e:
                logger.error(f"ActionExecutor raised exception for '{tool_name}': {e}", exc_info=True)
                return ActionResult(
                    success=False,
                    output=f"Controlled Error: Tool execution error: {e}",
                    tool_name=tool_name,
                    risk_tier=decision.risk_tier.value,
                    error=str(e),
                )

        duration_ms = (time.perf_counter() - start_time) * 1000
        is_success = (
            not exec_result.startswith("Security Error")
            and not exec_result.startswith("Controlled Error")
            and not exec_result.startswith("Action '")
            and "failed" not in exec_result.lower()
            and "denied" not in exec_result.lower()
            and "error" not in exec_result.lower()
        )

        return ActionResult(
            success=is_success,
            output=exec_result,
            tool_name=tool_name,
            requires_approval=False,
            approval_id=approval_id or decision.approval_id,
            risk_tier=decision.risk_tier.value,
            execution_metadata={"duration_ms": duration_ms},
        )

    def handle_approval(
        self,
        approval_id: str,
        approved: bool,
        context: SecurityContext,
    ) -> OrchestratorResponse:
        """
        Process human-in-the-loop decision for a pending action or deferred agent turn.
        """
        start_time = time.perf_counter()
        req_id = getattr(context, "request_id", None) or f"req_{int(time.time()*1000)}"

        try:
            ctx = self.validate_context(context)
            req_id = ctx.request_id
        except SecurityContextError as sce:
            return OrchestratorResponse(
                request_id=req_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Security Error: {sce}",
                error=str(sce),
                context=context,
                execution_metadata={"failure_category": "security_violation"},
            )

        # Enforce approver authorization via identity provider
        if not identity_manager.can_user_approve(ctx.user_id):
            audit_logger.log_event(
                event_type="UNAUTHORIZED_APPROVER_BLOCKED",
                approval_id=approval_id,
                actor=ctx.user_id,
                session_id=ctx.session_id,
                status="BLOCKED",
                details={"reason": f"User '{ctx.user_id}' is not authorized to grant approvals."},
            )
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Security Error: User '{ctx.user_id}' is not authorized to grant approvals.",
                error="Unauthorized approver",
                approval_id=approval_id,
                context=ctx,
                execution_metadata={"failure_category": "unauthorized_approver"},
            )

        # Check if approval belongs to a paused PydanticAI agent run
        if approval_id in self._deferred_runs:
            run_result, original_ctx = self._deferred_runs.pop(approval_id)
            try:
                resumed = self.pydantic_agent.resume_with_approval(
                    run_result=run_result,
                    request_id=approval_id,
                    approved=approved,
                    session_id=ctx.session_id,
                    actor=ctx.user_id,
                    context=ctx,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                status = OrchestrationStatus.SUCCESS if approved else OrchestrationStatus.DENIED
                return OrchestratorResponse(
                    request_id=ctx.request_id,
                    status=status,
                    response_text=str(resumed.output),
                    approval_id=approval_id,
                    context=ctx,
                    execution_metadata={"duration_ms": duration_ms},
                )
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"Failed to resume agent run with approval: {e}", exc_info=True)
                return OrchestratorResponse(
                    request_id=ctx.request_id,
                    status=OrchestrationStatus.ERROR,
                    response_text=f"Failed to resume action: {e}",
                    error=str(e),
                    approval_id=approval_id,
                    context=ctx,
                    execution_metadata={"duration_ms": duration_ms, "failure_category": "resume_failure"},
                )

        # Otherwise, resolve standalone approval request
        req = self.approval_manager.get_request(approval_id)
        if not req:
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.ERROR,
                response_text=f"No pending approval request found for ID '{approval_id}'.",
                error="Unknown approval ID",
                context=ctx,
            )

        if req.status == ApprovalStatus.EXPIRED or req.is_expired():
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.ERROR,
                response_text=f"Approval request '{approval_id}' has expired.",
                error="Approval expired",
                approval_id=approval_id,
                context=ctx,
            )

        if req.status == ApprovalStatus.CANCELLED:
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Approval request '{approval_id}' has been cancelled.",
                error="Approval cancelled",
                approval_id=approval_id,
                context=ctx,
            )

        if req.status == ApprovalStatus.CONSUMED:
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.BLOCKED,
                response_text=f"Security violation: Approval token '{approval_id}' has already been consumed (replay blocked).",
                error="Replay attack detected",
                approval_id=approval_id,
                context=ctx,
            )

        success, msg = self.approval_manager.resolve_request(
            request_id=approval_id,
            approved=approved,
            actor=ctx.user_id,
        )

        if not approved:
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.DENIED,
                response_text=f"Action '{req.tool_name}' was denied by {ctx.user_id}.",
                approval_id=approval_id,
                tool_name=req.tool_name,
                context=ctx,
            )

        if not success:
            return OrchestratorResponse(
                request_id=ctx.request_id,
                status=OrchestrationStatus.ERROR,
                response_text=f"Could not resolve approval: {msg}",
                error=msg,
                approval_id=approval_id,
                context=ctx,
            )

        # Execute approved action
        action_res = self.execute_action(
            tool_name=req.tool_name,
            arguments=req.arguments,
            context=ctx,
            approval_id=approval_id,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        return OrchestratorResponse(
            request_id=ctx.request_id,
            status=OrchestrationStatus.SUCCESS if action_res.success else OrchestrationStatus.ERROR,
            response_text=action_res.output,
            tool_name=req.tool_name,
            arguments=req.arguments,
            approval_id=approval_id,
            tool_results=[action_res],
            context=ctx,
            execution_metadata={"duration_ms": duration_ms},
        )


# Global orchestrator singleton instance
orchestrator = SonOrchestrator()
