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
from typing import Any, Union
from pydantic_ai import Agent, Tool, DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelMessage

from core.security.policy import SYSTEM_INSTRUCTIONS_POLICY, RiskTier
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger, canonical_args_hash
from core.security.sanitizer import wrap_untrusted_content
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
)
from services.sandbox.e2b_service import sandbox_service


# Tool Handler Implementations
def execute_python_code(params: ExecuteCodeParams) -> str:
    """Execute Python code strictly within an isolated E2B microVM sandbox."""
    res = sandbox_service.execute_code(code=params.code, timeout=params.timeout)
    if res.success:
        output = res.stdout if res.stdout else "Code executed successfully with no output."
        return wrap_untrusted_content(output, source="e2b:sandbox", source_type="code_output")
    return f"Sandbox Execution Error:\n{res.stderr or res.error_message}"


def execute_sandbox_command(params: ExecuteSandboxCommandParams) -> str:
    """Execute a terminal command strictly within an isolated E2B microVM sandbox."""
    res = sandbox_service.execute_terminal_command(command=params.command, timeout=params.timeout)
    if res.success:
        output = res.stdout if res.stdout else "Command completed with no output."
        return wrap_untrusted_content(output, source="e2b:command", source_type="command_output")
    return f"Sandbox Command Error (Exit {res.exit_code}):\n{res.stderr or res.error_message}"


def read_file_safe(params: ReadFileParams) -> str:
    """Read contents of a local file and wrap it in defensive security tags."""
    from tools.windows_control import read_file
    content = read_file(path=params.path, max_lines=params.max_lines)
    return wrap_untrusted_content(content, source=f"file:{params.path}", source_type="local_file")


def write_file_safe(params: WriteFileParams) -> str:
    """Write text to a local file."""
    from tools.windows_control import write_file
    return write_file(path=params.path, content=params.content)


def delete_path_safe(params: DeletePathParams) -> str:
    """Permanently delete a local file or folder. Requires human approval."""
    from plugins.files import FilesPlugin
    plugin = FilesPlugin()
    return plugin.delete_path(path=params.path)


def open_application_safe(params: OpenAppParams) -> str:
    """Open a permitted desktop application."""
    from tools.windows_control import open_application
    return open_application(name=params.name)


def close_application_safe(params: CloseAppParams) -> str:
    """Close a running application. Requires human approval."""
    from tools.windows_control import close_application
    return close_application(name=params.name)


def set_volume_safe(params: SetVolumeParams) -> str:
    """Set system audio volume."""
    from tools.windows_control import set_volume
    return set_volume(level=params.level)


def set_brightness_safe(params: SetBrightnessParams) -> str:
    """Set screen brightness."""
    from tools.windows_control import set_brightness
    return set_brightness(level=params.level)


def web_search_safe(params: WebSearchParams) -> str:
    """Search the web and wrap results in defensive security tags."""
    from tools.web import web_search
    results = web_search(query=params.query, max_results=params.max_results)
    return wrap_untrusted_content(results, source="duckduckgo:search", source_type="web_search")


def read_webpage_safe(params: ReadWebpageParams) -> str:
    """Read a webpage and wrap text in defensive security tags."""
    from tools.web import read_webpage
    content = read_webpage(url=params.url)
    return wrap_untrusted_content(content, source=params.url, source_type="webpage")


def shutdown_pc_safe(params: ShutdownPCParams) -> str:
    """Schedule system shutdown. Requires human approval."""
    from tools.windows_control import shutdown_pc
    return shutdown_pc(delay_seconds=params.delay_seconds)


class DefensivePydanticAgent:
    """
    Defensive PydanticAI Agent wrapper managing model initialization,
    tool approvals, server-side cryptographic audit records, and safe execution.
    """

    def __init__(self, model: Any = None):
        self.system_prompt = SYSTEM_INSTRUCTIONS_POLICY
        self.model = model

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
            Tool(web_search_safe, name="web_search", description="Search web via DuckDuckGo.", requires_approval=False),
            Tool(read_webpage_safe, name="read_webpage", description="Fetch webpage text.", requires_approval=False),
        ]

        self.agent = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=self.tools,
            output_type=Union[str, DeferredToolRequests],
        )

        # Mapping of call_id to approval_request_id for active runs
        self._call_to_request: dict[str, str] = {}

    def run(
        self,
        user_prompt: str,
        session_id: str = "default_session",
        message_history: list[ModelMessage] | None = None,
    ) -> Any:
        """
        Execute an agent turn with deferred tool approval interception.
        """
        audit_logger.log_event(
            event_type="AGENT_RUN_START",
            session_id=session_id,
            details={"prompt_preview": user_prompt[:150]},
        )

        run_result = self.agent.run_sync(
            user_prompt=user_prompt,
            message_history=message_history,
        )

        # Check if the run paused on deferred tool approval
        if isinstance(run_result.output, DeferredToolRequests):
            deferred_requests: DeferredToolRequests = run_result.output
            for call_part in deferred_requests.approvals:
                # Record server-side approval request bound to SHA-256 argument hash
                req = approval_manager.create_request(
                    tool_name=call_part.tool_name,
                    arguments=call_part.args if isinstance(call_part.args, dict) else {},
                    session_id=session_id,
                    risk_level=RiskTier.HIGH,
                )
                self._call_to_request[call_part.tool_call_id] = req.request_id

                audit_logger.log_event(
                    event_type="DEFERRED_TOOL_APPROVAL_PAUSED",
                    tool_name=call_part.tool_name,
                    arguments=call_part.args if isinstance(call_part.args, dict) else {},
                    risk_level="HIGH",
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
        actor: str = "user",
    ) -> Any:
        """
        Resume an agent turn that paused on deferred approval.
        Validates server-side request status and argument hash before continuing.
        """
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
            valid, reason = approval_manager.verify_and_consume(request_id, req.arguments)
            if not valid:
                raise ValueError(f"Security validation failed: {reason}")

        # 3. Resume PydanticAI execution with DeferredToolResults
        approval_dict = {target_call_id: approved}
        deferred_results = DeferredToolResults(approvals=approval_dict)

        resume_result = self.agent.run_sync(
            message_history=run_result.all_messages(),
            deferred_tool_results=deferred_results,
        )

        # Cleanup mapping
        self._call_to_request.pop(target_call_id, None)

        audit_logger.log_event(
            event_type="AGENT_RUN_RESUMED",
            session_id=session_id,
            approval_id=request_id,
            status="RESUMED",
            details={"approved": approved},
        )
        return resume_result
