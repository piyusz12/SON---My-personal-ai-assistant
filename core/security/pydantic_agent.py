# core/security/pydantic_agent.py — Defensive PydanticAI Agent Implementation
"""
Defensive PydanticAI Agent Architecture for SON v3:
  1. Centralized system instruction configuration enforcing application security policy.
  2. Pydantic-validated tool definitions with risk tiers.
  3. First-class deferred tool approval (requires_approval=True, DeferredToolRequests, DeferredToolResults).
  4. Server-side approval binding with cryptographic argument hashes and replay prevention.
  5. Isolated E2B microVM code execution without host shell fallback.
  6. Automatic untrusted content wrapping and prompt injection defense on external outputs.
"""

import os
import contextvars
from typing import Any, Union
from pydantic_ai import Agent, Tool, DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelMessage

from core.security.policy import SYSTEM_INSTRUCTIONS_POLICY, RiskTier
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger, canonical_args_hash
from core.security.sanitizer import wrap_untrusted_content
from core.config import SecurityLevel
from core.action_executor import ActionExecutor
from core.security.tool_registry import defensive_tool_registry
from core.security.context import SecurityContext, SecurityContextError
from core.security.schemas import (
    ExecuteCodeParams,
    ExecuteSandboxCommandParams,
    ReadFileParams,
    WriteFileParams,
    DeletePathParams,
    OpenAppParams,
    CloseAppParams,
    SetVolumeParams,
    SetBrightnessParams,
    WebSearchParams,
    ReadWebpageParams,
    ShutdownPCParams,
    DatabaseQueryParams,
    ListDirectoryParams,
    SearchFilesParams,
)
from services.sandbox.e2b_service import sandbox_service


# Shared ActionExecutor for agent tools
_agent_action_executor = ActionExecutor()

# Thread-safe execution context for the active agent turn
_active_agent_context: contextvars.ContextVar[tuple[Any | None, Any | None]] = contextvars.ContextVar(
    "_active_agent_context", default=(None, None)
)


def _dispatch_agent_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Mandatory execution path for PydanticAI tools:
    1. Resolve tool definition through DefensiveToolRegistry.
    2. Check for pre-verified approval ticket from deferred resume.
    3. Execute strictly through ActionExecutor with SecurityContext and Policy gating.
    """
    agent, ctx = _active_agent_context.get()
    executor = getattr(agent, "executor", None) or _agent_action_executor

    # 1. Resolve through DefensiveToolRegistry
    reg_tool = defensive_tool_registry.get_tool(tool_name)
    if not reg_tool:
        err = f"Security Error: Tool '{tool_name}' is not registered in DefensiveToolRegistry."
        audit_logger.log_event(
            event_type="UNREGISTERED_TOOL_CALLED",
            tool_name=tool_name,
            arguments=arguments,
            actor=getattr(ctx, "user_id", "primary_user"),
            session_id=getattr(ctx, "session_id", "default_session"),
            status="REJECTED",
        )
        return err

    # 2. Check for pre-verified approval token
    approval_id = None
    already_approved = False
    if agent and hasattr(agent, "_resumed_approvals") and tool_name in agent._resumed_approvals:
        approval_id = agent._resumed_approvals.pop(tool_name)
        already_approved = True

    # 3. Security Level Mapping
    sec_level = SecurityLevel.SAFE
    if reg_tool.risk_tier == RiskTier.HIGH:
        sec_level = SecurityLevel.CRITICAL
    elif reg_tool.risk_tier == RiskTier.MEDIUM:
        sec_level = SecurityLevel.MEDIUM

    # 4. Execute strictly through ActionExecutor
    return executor.execute(
        tool_name=tool_name,
        arguments=arguments,
        tool_func=reg_tool.handler,
        security_level=sec_level,
        context=ctx,
        approval_id=approval_id,
        already_approved=already_approved,
    )


# Tool Handler Implementations (All route through DefensiveToolRegistry + ActionExecutor)
def execute_python_code(params: ExecuteCodeParams) -> str:
    """Execute Python code strictly within an isolated E2B microVM sandbox."""
    return _dispatch_agent_tool("execute_python_code", params.model_dump())


def execute_sandbox_command(params: ExecuteSandboxCommandParams) -> str:
    """Execute a terminal command strictly within an isolated E2B microVM sandbox."""
    return _dispatch_agent_tool("execute_sandbox_command", params.model_dump())


def read_file_safe(params: ReadFileParams) -> str:
    """Read contents of a local file and wrap it in defensive security tags."""
    return _dispatch_agent_tool("read_file", params.model_dump())


def write_file_safe(params: WriteFileParams) -> str:
    """Write text to a local file."""
    return _dispatch_agent_tool("write_file", params.model_dump())


def delete_path_safe(params: DeletePathParams) -> str:
    """Permanently delete a local file or folder. Requires human approval."""
    return _dispatch_agent_tool("delete_path", params.model_dump())


def open_application_safe(params: OpenAppParams) -> str:
    """Open a permitted desktop application."""
    return _dispatch_agent_tool("open_application", params.model_dump())


def close_application_safe(params: CloseAppParams) -> str:
    """Close a running application. Requires human approval."""
    return _dispatch_agent_tool("close_application", params.model_dump())


def set_volume_safe(params: SetVolumeParams) -> str:
    """Set system audio volume."""
    return _dispatch_agent_tool("set_volume", params.model_dump())


def set_brightness_safe(params: SetBrightnessParams) -> str:
    """Set screen brightness."""
    return _dispatch_agent_tool("set_brightness", params.model_dump())


def web_search_safe(params: WebSearchParams) -> str:
    """Search the web and wrap results in defensive security tags."""
    return _dispatch_agent_tool("web_search", params.model_dump())


def read_webpage_safe(params: ReadWebpageParams) -> str:
    """Read a webpage and wrap text in defensive security tags."""
    return _dispatch_agent_tool("read_webpage", params.model_dump())


def shutdown_pc_safe(params: ShutdownPCParams) -> str:
    """Schedule system shutdown. Requires human approval."""
    return _dispatch_agent_tool("shutdown_pc", params.model_dump())


def restart_pc_safe(params: ShutdownPCParams) -> str:
    """Schedule system restart. Requires human approval."""
    return _dispatch_agent_tool("restart_pc", params.model_dump())


def list_directory_safe(params: ListDirectoryParams) -> str:
    """List contents of an approved workspace directory."""
    return _dispatch_agent_tool("list_directory", params.model_dump())


def search_files_safe(params: SearchFilesParams) -> str:
    """Search for files matching pattern in approved workspace directories."""
    return _dispatch_agent_tool("search_files", params.model_dump())


def database_query_safe(params: DatabaseQueryParams) -> str:
    """Execute a controlled SQL query against local SQLite database."""
    return _dispatch_agent_tool("database_query", params.model_dump())


class DefensivePydanticAgent:
    """
    Defensive PydanticAI Agent wrapper managing model initialization,
    tool approvals, server-side cryptographic audit records, and safe execution.
    """

    def __init__(self, model: Any = None, executor: ActionExecutor | None = None):
        self.system_prompt = SYSTEM_INSTRUCTIONS_POLICY
        self.model = model
        self.executor = executor or _agent_action_executor

        # Define tools with appropriate approval gating
        self.tools = [
            Tool(execute_python_code, name="execute_python_code", description="Execute code inside isolated E2B microVM.", requires_approval=False),
            Tool(execute_sandbox_command, name="execute_sandbox_command", description="Run command inside isolated E2B microVM.", requires_approval=False),
            Tool(read_file_safe, name="read_file", description="Read local file contents.", requires_approval=False),
            Tool(write_file_safe, name="write_file", description="Write content to a file.", requires_approval=False),
            Tool(delete_path_safe, name="delete_path", description="Delete file or folder permanently. HIGH RISK.", requires_approval=True),
            Tool(open_application_safe, name="open_application", description="Open desktop app.", requires_approval=False),
            Tool(close_application_safe, name="close_application", description="Close running desktop app. HIGH RISK.", requires_approval=True),
            Tool(set_volume_safe, name="set_volume", description="Set audio volume level.", requires_approval=False),
            Tool(set_brightness_safe, name="set_brightness", description="Set screen brightness level.", requires_approval=False),
            Tool(shutdown_pc_safe, name="shutdown_pc", description="Shutdown PC workstation. HIGH RISK.", requires_approval=True),
            Tool(restart_pc_safe, name="restart_pc", description="Restart PC workstation. HIGH RISK.", requires_approval=True),
            Tool(web_search_safe, name="web_search", description="Search web via DuckDuckGo.", requires_approval=False),
            Tool(read_webpage_safe, name="read_webpage", description="Fetch webpage text.", requires_approval=False),
            Tool(list_directory_safe, name="list_directory", description="List files in approved workspace directory.", requires_approval=False),
            Tool(search_files_safe, name="search_files", description="Search files matching pattern in workspace.", requires_approval=False),
            Tool(database_query_safe, name="database_query", description="Execute controlled SQL query.", requires_approval=False),
        ]

        self.agent = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=self.tools,
            output_type=Union[str, DeferredToolRequests],
        )

        # Mapping of call_id to approval_request_id for active runs
        self._call_to_request: dict[str, str] = {}
        # Mapping of tool_name to approval_request_id for resumed tool calls
        self._resumed_approvals: dict[str, str] = {}

    def run(
        self,
        user_prompt: str,
        session_id: str = "default_session",
        context: SecurityContext | None = None,
        message_history: list[ModelMessage] | None = None,
    ) -> Any:
        """
        Execute an agent turn with deferred tool approval interception.
        """
        if context is not None:
            if not context.is_authenticated:
                audit_logger.log_event(
                    event_type="UNAUTHENTICATED_AGENT_RUN_BLOCKED",
                    actor=context.user_id,
                    session_id=context.session_id,
                    status="BLOCKED",
                )
                raise SecurityContextError("Unauthenticated security context is rejected.")
            session_id = context.session_id
            user_id = context.user_id
        else:
            user_id = "primary_user"

        audit_logger.log_event(
            event_type="AGENT_RUN_START",
            actor=user_id,
            session_id=session_id,
            details={"prompt_preview": user_prompt[:150]},
        )

        c_token = _active_agent_context.set((self, context))
        try:
            run_result = self.agent.run_sync(
                user_prompt=user_prompt,
                message_history=message_history,
            )
        finally:
            _active_agent_context.reset(c_token)

        # Check if the run paused on deferred tool approval
        if isinstance(run_result.output, DeferredToolRequests):
            deferred_requests: DeferredToolRequests = run_result.output
            for call_part in deferred_requests.approvals:
                # Record server-side approval request bound to SHA-256 argument hash, user, and session
                req = approval_manager.create_request(
                    tool_name=call_part.tool_name,
                    arguments=call_part.args if isinstance(call_part.args, dict) else {},
                    session_id=session_id,
                    user_id=user_id,
                    risk_level=RiskTier.HIGH,
                )
                self._call_to_request[call_part.tool_call_id] = req.request_id

                audit_logger.log_event(
                    event_type="DEFERRED_TOOL_APPROVAL_PAUSED",
                    tool_name=call_part.tool_name,
                    arguments=call_part.args if isinstance(call_part.args, dict) else {},
                    risk_level="HIGH",
                    actor=user_id,
                    session_id=session_id,
                    approval_id=req.request_id,
                    status="AWAITING_APPROVAL",
                    details={"tool_call_id": call_part.tool_call_id},
                )

        return run_result

    def resume_with_approval(
        self,
        run_result: Any,
        request_id: str,
        approved: bool,
        session_id: str = "default_session",
        actor: str = "primary_user",
        context: SecurityContext | None = None,
    ) -> Any:
        """
        Resume an agent turn that paused on deferred approval.
        Validates server-side request status and argument hash before continuing.
        """
        if context is not None:
            if not context.is_authenticated:
                raise SecurityContextError("Unauthenticated security context is rejected.")
            session_id = context.session_id
            actor = context.user_id

        # 1. Resolve server-side request
        success, msg = approval_manager.resolve_request(request_id, approved=approved, actor=actor)
        if not success and approved:
            raise ValueError(f"Cannot resume agent run: {msg}")

        # 2. Find matching tool_call_id
        target_call_id = None
        for call_id, req_id in list(self._call_to_request.items()):
            if req_id == request_id:
                target_call_id = call_id
                break

        if not target_call_id:
            raise ValueError(f"No pending agent tool call matches approval request ID: {request_id}")

        req = approval_manager.get_request(request_id)
        if approved and req:
            valid, reason = approval_manager.verify_and_consume(
                request_id,
                req.arguments,
                tool_name=req.tool_name,
                session_id=session_id,
                user_id=actor,
            )
            if not valid:
                raise ValueError(f"Security validation failed: {reason}")
            # Mark tool call as approved for execution
            self._resumed_approvals[req.tool_name] = request_id

        # 3. Resume PydanticAI execution with DeferredToolResults
        approval_dict = {target_call_id: approved}
        deferred_results = DeferredToolResults(approvals=approval_dict)

        c_token = _active_agent_context.set((self, context))
        try:
            resume_result = self.agent.run_sync(
                message_history=run_result.all_messages(),
                deferred_tool_results=deferred_results,
            )
        finally:
            _active_agent_context.reset(c_token)

        # Cleanup mapping
        self._call_to_request.pop(target_call_id, None)

        audit_logger.log_event(
            event_type="AGENT_RUN_RESUMED",
            actor=actor,
            session_id=session_id,
            approval_id=request_id,
            status="RESUMED",
            details={"approved": approved},
        )
        return resume_result

