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
import logging
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field
from pydantic_ai import DeferredToolRequests

from core.config import Config, SecurityLevel
from core.action_executor import ActionExecutor
from core.security.context import SecurityContext, SecurityContextError, create_trusted_context
from core.security.policy import RiskTier, classify_risk
from core.security.policy_engine import SecurityPolicyEngine, policy_engine
from core.security.approval_manager import ApprovalManager, approval_manager, ApprovalStatus
from core.security.audit_logger import SecurityAuditLogger, audit_logger, redact_secrets
from core.security.sanitizer import detect_prompt_injection, wrap_untrusted_content
from core.security.tool_registry import DefensiveToolRegistry, defensive_tool_registry
from core.security.pydantic_agent import DefensivePydanticAgent

logger = Config.get_logger(__name__)


class OrchestrationStatus(str, Enum):
    SUCCESS = "success"
    AWAITING_APPROVAL = "awaiting_approval"
    DENIED = "denied"
    BLOCKED = "blocked"
    ERROR = "error"


class ActionResult(BaseModel):
    """Result of an action execution through the security pipeline."""
    success: bool
    output: str
    tool_name: str
    requires_approval: bool = False
    approval_id: Optional[str] = None
    risk_tier: str = "low"
    error: Optional[str] = None


class OrchestrationResult(BaseModel):
    """Structured response from the central orchestrator to the calling interface."""
    status: OrchestrationStatus
    text: str
    tool_name: Optional[str] = None
    arguments: Optional[dict[str, Any]] = None
    approval_id: Optional[str] = None
    action_result: Optional[ActionResult] = None
    context: Optional[SecurityContext] = None
    details: dict[str, Any] = Field(default_factory=dict)


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
    ):
        self.action_executor = action_executor or ActionExecutor(ui=ui)
        self.pydantic_agent = pydantic_agent or DefensivePydanticAgent(executor=self.action_executor)
        self.policy_engine = policy_engine_instance or policy_engine
        self.tool_registry = tool_registry or defensive_tool_registry
        self.approval_manager = approval_manager_instance or approval_manager
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

        if not context.is_authenticated:
            audit_logger.log_event(
                event_type="UNAUTHENTICATED_SECURITY_CONTEXT_BLOCKED",
                actor=context.user_id,
                session_id=context.session_id,
                status="BLOCKED",
            )
            raise SecurityContextError(f"SecurityContext for user '{context.user_id}' is not authenticated.")

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
    ) -> OrchestrationResult:
        """
        Central processing pipeline for all user requests across all interfaces.

        Flow:
          1. SecurityContext validation
          2. Prompt injection detection
          3. Fast-path deterministic command handling (via secure ActionExecutor)
          4. Defensive PydanticAI Agent execution
          5. Tool approval gating or execution
          6. Result formatting and audit logging
        """
        # 1. Enforce trusted security context
        try:
            ctx = self.validate_context(context)
        except SecurityContextError as sce:
            return OrchestrationResult(
                status=OrchestrationStatus.BLOCKED,
                text=f"Security Error: {sce}",
                details={"error": str(sce)},
            )

        audit_logger.log_event(
            event_type="ORCHESTRATOR_REQUEST_RECEIVED",
            actor=ctx.user_id,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            status="PROCESSING",
            details={
                "interface_type": ctx.interface_type,
                "input_preview": text[:120],
            },
        )

        # 2. Prompt injection screening
        is_injection, injection_types = detect_prompt_injection(text)
        if is_injection:
            audit_logger.log_event(
                event_type="PROMPT_INJECTION_FLAGGED",
                actor=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                status="FLAGGED",
                details={"injection_types": injection_types, "input_preview": text[:150]},
            )
            logger.warning(f"Prompt injection patterns detected from {ctx.user_id}: {injection_types}")

        # 3. Deterministic Command Handling (Pattern-matched commands route through orchestrator)
        if self.command_handler and hasattr(self.command_handler, "handle"):
            # Check if command_handler handles this text
            handled, cmd_result = self.command_handler.handle(text)
            if handled:
                audit_logger.log_event(
                    event_type="COMMAND_HANDLER_EXECUTED",
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    request_id=ctx.request_id,
                    status="SUCCESS",
                    details={"text": text[:80]},
                )
                return OrchestrationResult(
                    status=OrchestrationStatus.SUCCESS,
                    text=cmd_result or "Command executed.",
                    context=ctx,
                )

        # 4. Defensive PydanticAI Agent Execution
        try:
            run_result = self.pydantic_agent.run(
                user_prompt=text,
                session_id=ctx.session_id,
                context=ctx,
            )
        except SecurityContextError as sce:
            return OrchestrationResult(
                status=OrchestrationStatus.BLOCKED,
                text=f"Security Error: {sce}",
                context=ctx,
            )
        except Exception as e:
            logger.error(f"Error during PydanticAI agent turn: {e}", exc_info=True)
            audit_logger.log_event(
                event_type="AGENT_EXECUTION_ERROR",
                actor=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                status="ERROR",
                details={"error": str(e)},
            )
            return OrchestrationResult(
                status=OrchestrationStatus.ERROR,
                text=f"An error occurred while processing your request: {e}",
                context=ctx,
            )

        # 5. Deferred Approval Handling
        if isinstance(run_result.output, DeferredToolRequests):
            deferred: DeferredToolRequests = run_result.output
            if deferred.approvals:
                first_approval = deferred.approvals[0]
                call_id = first_approval.tool_call_id
                req_id = self.pydantic_agent._call_to_request.get(call_id)
                tool_name = first_approval.tool_name
                args = first_approval.args if isinstance(first_approval.args, dict) else {}

                if req_id:
                    self._deferred_runs[req_id] = (run_result, ctx)

                approval_prompt = (
                    f"Action '{tool_name}' requires Dad's explicit authorization. "
                    f"Arguments: {redact_secrets(args)}. Approve? (ID: {req_id})"
                )

                audit_logger.log_event(
                    event_type="ORCHESTRATOR_AWAITING_APPROVAL",
                    actor=ctx.user_id,
                    session_id=ctx.session_id,
                    request_id=ctx.request_id,
                    tool_name=tool_name,
                    approval_id=req_id,
                    status="AWAITING_APPROVAL",
                )

                return OrchestrationResult(
                    status=OrchestrationStatus.AWAITING_APPROVAL,
                    text=approval_prompt,
                    tool_name=tool_name,
                    arguments=args,
                    approval_id=req_id,
                    context=ctx,
                )

        # 6. Completed Agent Turn
        final_text = str(run_result.output)
        audit_logger.log_event(
            event_type="ORCHESTRATOR_REQUEST_COMPLETED",
            actor=ctx.user_id,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            status="SUCCESS",
        )
        return OrchestrationResult(
            status=OrchestrationStatus.SUCCESS,
            text=final_text,
            context=ctx,
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
                    output=f"Action '{tool_name}' requires approval. Request ID: {decision.approval_id}",
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

        # 4. Execute through ActionExecutor
        exec_result = self.action_executor.execute(
            tool_name=tool_name,
            arguments=arguments,
            tool_func=handler,
            security_level=sec_level,
            context=ctx,
            approval_id=approval_id or decision.approval_id,
            already_approved=decision.allowed,
        )

        return ActionResult(
            success=not exec_result.startswith("Security Error") and not exec_result.startswith("Action '") and "denied" not in exec_result.lower(),
            output=exec_result,
            tool_name=tool_name,
            requires_approval=False,
            approval_id=approval_id or decision.approval_id,
            risk_tier=decision.risk_tier.value,
        )

    def handle_approval(
        self,
        approval_id: str,
        approved: bool,
        context: SecurityContext,
    ) -> OrchestrationResult:
        """
        Process human-in-the-loop decision for a pending action or deferred agent turn.
        """
        try:
            ctx = self.validate_context(context)
        except SecurityContextError as sce:
            return OrchestrationResult(
                status=OrchestrationStatus.BLOCKED,
                text=f"Security Error: {sce}",
                context=context,
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
                status = OrchestrationStatus.SUCCESS if approved else OrchestrationStatus.DENIED
                return OrchestrationResult(
                    status=status,
                    text=str(resumed.output),
                    approval_id=approval_id,
                    context=ctx,
                )
            except Exception as e:
                logger.error(f"Failed to resume agent run with approval: {e}", exc_info=True)
                return OrchestrationResult(
                    status=OrchestrationStatus.ERROR,
                    text=f"Failed to resume action: {e}",
                    approval_id=approval_id,
                    context=ctx,
                )

        # Otherwise, resolve standalone approval request
        req = self.approval_manager.get_request(approval_id)
        if not req:
            return OrchestrationResult(
                status=OrchestrationStatus.ERROR,
                text=f"No pending approval request found for ID '{approval_id}'.",
                context=ctx,
            )

        success, msg = self.approval_manager.resolve_request(
            request_id=approval_id,
            approved=approved,
            actor=ctx.user_id,
        )

        if not success:
            return OrchestrationResult(
                status=OrchestrationStatus.ERROR,
                text=f"Could not resolve approval: {msg}",
                approval_id=approval_id,
                context=ctx,
            )

        if not approved:
            return OrchestrationResult(
                status=OrchestrationStatus.DENIED,
                text=f"Action '{req.tool_name}' was denied by {ctx.user_id}.",
                approval_id=approval_id,
                tool_name=req.tool_name,
                context=ctx,
            )

        # Execute approved action
        action_res = self.execute_action(
            tool_name=req.tool_name,
            arguments=req.arguments,
            context=ctx,
            approval_id=approval_id,
        )

        return OrchestrationResult(
            status=OrchestrationStatus.SUCCESS if action_res.success else OrchestrationStatus.ERROR,
            text=action_res.output,
            tool_name=req.tool_name,
            arguments=req.arguments,
            approval_id=approval_id,
            action_result=action_res,
            context=ctx,
        )


# Global orchestrator singleton instance
orchestrator = SonOrchestrator()
