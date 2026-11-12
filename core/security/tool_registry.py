# core/security/tool_registry.py — Defensive Agent Tool Registry with Pydantic Validation
"""
Controlled Agent Tool Registry enforcing:
  1. Strict Pydantic model argument validation.
  2. Risk tier classification & mandatory approval gatekeeping for HIGH risk tools.
  3. Single-entry code execution inside isolated E2B microVM.
  4. Automatic untrusted content wrapping and prompt injection defense on tool outputs.
  5. Audit logging on every execution attempt.
"""

import json
import logging
from typing import Any, Callable, Type, Optional
from pydantic import BaseModel, ValidationError

from core.security.policy import RiskTier, classify_risk
from core.security.approval_manager import approval_manager, ApprovalStatus
from core.security.audit_logger import audit_logger, canonical_args_hash
from core.security.sanitizer import wrap_untrusted_content
from services.sandbox.e2b_service import sandbox_service

logger = logging.getLogger("son.security.registry")


class RegisteredTool:
    """Descriptor for a securely registered tool."""
    def __init__(
        self,
        name: str,
        handler: Callable,
        schema: Type[BaseModel],
        description: str,
        risk_tier: RiskTier,
        is_external_output: bool = False,
    ):
        self.name = name
        self.handler = handler
        self.schema = schema
        self.description = description
        self.risk_tier = risk_tier
        self.is_external_output = is_external_output


class DefensiveToolRegistry:
    """
    Central registry for defensive tools with Pydantic validation,
    cryptographic approval checks, and sandbox isolation.
    """

    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        schema: Type[BaseModel],
        description: str,
        risk_tier: RiskTier | None = None,
        is_external_output: bool = False,
    ):
        """Register a tool with its Pydantic schema and security configuration."""
        risk = risk_tier or classify_risk(name, {})
        self._tools[name] = RegisteredTool(
            name=name,
            handler=handler,
            schema=schema,
            description=description,
            risk_tier=risk,
            is_external_output=is_external_output,
        )

    def get_tool(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def get(self, name: str, default: Any = None) -> RegisteredTool | None:
        return self._tools.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __getitem__(self, name: str) -> RegisteredTool:
        return self._tools[name]

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_tier": t.risk_tier.value,
                "schema": t.schema.model_json_schema(),
            }
            for t in self._tools.values()
        ]

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        session_id: str = "default_session",
        approval_id: str | None = None,
        user_id: str = "primary_user",
        context: Any | None = None,
    ) -> tuple[bool, str]:
        """
        Secure tool dispatch workflow:
        1. Tool existence check
        2. Strict Pydantic model validation
        3. Risk tier authorization / Human-in-the-loop approval verification
        4. Safe execution
        5. Output sanitization & delimiter boundary wrapping
        6. Security audit logging
        """
        raw_args = arguments or {}
        if context is not None:
            if not getattr(context, "is_authenticated", True):
                audit_logger.log_event(
                    event_type="UNAUTHENTICATED_EXECUTION_BLOCKED",
                    tool_name=tool_name,
                    arguments=raw_args,
                    actor=getattr(context, "user_id", "unauthenticated"),
                    session_id=getattr(context, "session_id", "unknown_session"),
                    status="BLOCKED",
                )
                return False, f"Security Error: Unauthenticated context rejected for tool '{tool_name}'."
            user_id = getattr(context, "user_id", user_id)
            session_id = getattr(context, "session_id", session_id)

        tool = self.get_tool(tool_name)

        if not tool:
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
            return False, err

        # 1. Pydantic validation
        try:
            validated_model = tool.schema.model_validate(raw_args)
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
            return False, err

        # 2. Authorization & Human Approval Verification
        if tool.risk_tier == RiskTier.HIGH:
            if not approval_id:
                # Request required
                req = approval_manager.create_request(
                    tool_name=tool_name,
                    arguments=validated_args,
                    session_id=session_id,
                    user_id=user_id,
                    risk_level=tool.risk_tier,
                )
                err = (
                    f"Action '{tool_name}' classified as HIGH RISK requires explicit human approval. "
                    f"Approval request created with ID: {req.request_id}. Please confirm."
                )
                return False, err

            # Verify and consume approval ticket with strict binding
            valid, reason = approval_manager.verify_and_consume(
                approval_id,
                validated_args,
                tool_name=tool_name,
                session_id=session_id,
                user_id=user_id,
            )
            if not valid:
                return False, f"Authorization failed: {reason}"

        # 3. Execution
        try:
            audit_logger.log_event(
                event_type="TOOL_EXECUTION_START",
                tool_name=tool_name,
                arguments=validated_args,
                actor=user_id,
                risk_level=tool.risk_tier.value,
                session_id=session_id,
                approval_id=approval_id,
                status="EXECUTING",
            )

            result = tool.handler(**validated_args)

            # Ensure string output
            if result is None:
                output_str = "Completed successfully."
            elif isinstance(result, (dict, list)):
                output_str = json.dumps(result, indent=2, default=str)
            else:
                output_str = str(result)

            # 4. Untrusted Content Boundary Wrapping (for external/read resources)
            if tool.is_external_output:
                output_str = wrap_untrusted_content(
                    content=output_str,
                    source=f"tool:{tool_name}",
                    source_type="tool_output",
                    session_id=session_id,
                )

            audit_logger.log_event(
                event_type="TOOL_EXECUTION_SUCCESS",
                tool_name=tool_name,
                arguments=validated_args,
                actor=user_id,
                risk_level=tool.risk_tier.value,
                session_id=session_id,
                approval_id=approval_id,
                status="SUCCESS",
                details={"output_length": len(output_str)},
            )
            return True, output_str

        except Exception as exc:
            err = f"Execution error in tool '{tool_name}': {exc}"
            audit_logger.log_event(
                event_type="TOOL_EXECUTION_EXCEPTION",
                tool_name=tool_name,
                arguments=validated_args,
                actor=user_id,
                risk_level=tool.risk_tier.value,
                session_id=session_id,
                approval_id=approval_id,
                status="ERROR",
                details={"exception": str(exc)},
            )
            return False, err


# Standard tool implementation wrappers
def _tool_execute_code(code: str, timeout: int = 30) -> str:
    """Execute code strictly inside E2B isolated sandbox."""
    res = sandbox_service.execute_code(code=code, timeout=timeout)
    if res.success:
        return res.stdout if res.stdout else "Code executed successfully with no output."
    return f"Execution Error:\n{res.stderr or res.error_message}"


def _tool_execute_sandbox_command(command: str, timeout: int = 30) -> str:
    """Execute shell command strictly inside E2B isolated sandbox."""
    res = sandbox_service.execute_terminal_command(command=command, timeout=timeout)
    if res.success:
        return res.stdout if res.stdout else "Command completed with no output."
    return f"Command Error (Exit {res.exit_code}):\n{res.stderr or res.error_message}"


def create_default_defensive_registry() -> DefensiveToolRegistry:
    """Build and populate the default defensive tool registry."""
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
        GetWeatherParams,
        GetNewsParams,
        OpenWebsiteParams,
        DockerListContainersParams,
        DockerContainerActionParams,
        GetSystemInfoParams,
        TakeScreenshotParams,
        OpenWhatsAppDraftParams,
    )
    from tools import windows_control
    from tools import web
    from tools import docker_control
    from services.whatsapp.browser_launcher import BrowserLauncher
    from plugins.files import FilesPlugin
    from core.security.secure_file_service import secure_file_service
    from core.security.secure_database_service import secure_database_service

    files_plugin = FilesPlugin()
    registry = DefensiveToolRegistry()

    # 1. Isolated E2B Code Execution (Single approved path)
    registry.register(
        name="execute_python_code",
        handler=_tool_execute_code,
        schema=ExecuteCodeParams,
        description="Execute Python code safely inside an isolated E2B microVM sandbox.",
        risk_tier=RiskTier.MEDIUM,
        is_external_output=True,
    )
    registry.register(
        name="execute_sandbox_command",
        handler=_tool_execute_sandbox_command,
        schema=ExecuteSandboxCommandParams,
        description="Execute terminal command inside an isolated E2B microVM sandbox.",
        risk_tier=RiskTier.MEDIUM,
        is_external_output=True,
    )

    # 2. Local File Operations (Controlled & Gated via SecureFileService)
    def _safe_read_file(path: str, max_lines: int = 200) -> str:
        try:
            return secure_file_service.read_file(path=path, max_lines=max_lines)
        except Exception as e:
            return f"Security Error: Failed to read file '{path}': {e}"

    def _safe_write_file(path: str, content: str) -> str:
        try:
            return secure_file_service.write_file(path=path, content=content, overwrite=True)
        except Exception as e:
            return f"Security Error: Failed to write file '{path}': {e}"

    def _safe_delete_path(path: str) -> str:
        try:
            return secure_file_service.delete_path(path=path)
        except Exception as e:
            return f"Security Error: Failed to delete path '{path}': {e}"

    registry.register(
        name="read_file",
        handler=_safe_read_file,
        schema=ReadFileParams,
        description="Read lines from an approved local file safely.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,  # File contents are untrusted external data!
    )
    registry.register(
        name="write_file",
        handler=_safe_write_file,
        schema=WriteFileParams,
        description="Write text to an approved local file destination.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="delete_path",
        handler=_safe_delete_path,
        schema=DeletePathParams,
        description="Permanently delete a local file or directory. Requires explicit human approval.",
        risk_tier=RiskTier.HIGH,
    )

    # 3. System & Application Controls
    registry.register(
        name="open_application",
        handler=windows_control.open_application,
        schema=OpenAppParams,
        description="Open a permitted Windows application.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="close_application",
        handler=windows_control.close_application,
        schema=CloseAppParams,
        description="Close a running application. High-risk operation requiring approval.",
        risk_tier=RiskTier.HIGH,
    )
    registry.register(
        name="set_volume",
        handler=windows_control.set_volume,
        schema=SetVolumeParams,
        description="Set system audio volume.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="set_brightness",
        handler=windows_control.set_brightness,
        schema=SetBrightnessParams,
        description="Set screen brightness.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="shutdown_pc",
        handler=windows_control.shutdown_pc,
        schema=ShutdownPCParams,
        description="Schedule a system shutdown. High-risk operation requiring approval.",
        risk_tier=RiskTier.HIGH,
    )
    registry.register(
        name="restart_pc",
        handler=windows_control.restart_pc,
        schema=ShutdownPCParams,
        description="Schedule a system restart. High-risk operation requiring approval.",
        risk_tier=RiskTier.HIGH,
    )

    # 4. Web Information Retrieval
    registry.register(
        name="web_search",
        handler=web.web_search,
        schema=WebSearchParams,
        description="Search the web with DuckDuckGo.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )
    registry.register(
        name="read_webpage",
        handler=web.read_webpage,
        schema=ReadWebpageParams,
        description="Fetch and read webpage text content.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )

    # 5. Secure File & Database Exploration
    registry.register(
        name="list_directory",
        handler=secure_file_service.list_directory,
        schema=ListDirectoryParams,
        description="List files in approved workspace directory.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )
    registry.register(
        name="search_files",
        handler=secure_file_service.search_files,
        schema=SearchFilesParams,
        description="Search for files in approved workspace directory.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )
    registry.register(
        name="database_query",
        handler=secure_database_service.execute_query,
        schema=DatabaseQueryParams,
        description="Execute controlled parameterized SQL query against local SQLite database.",
        risk_tier=RiskTier.LOW,  # Dynamic evaluation promotes destructive queries to HIGH
        is_external_output=True,
    )

    # 6. Integrated Web, Docker, Hardware & Messaging Tools
    registry.register(
        name="get_weather",
        handler=lambda city="auto": web.get_weather(city),
        schema=GetWeatherParams,
        description="Get current weather for a city or current location.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )
    registry.register(
        name="get_news",
        handler=lambda topic="technology": web.get_news(topic),
        schema=GetNewsParams,
        description="Get top news headlines for a topic.",
        risk_tier=RiskTier.LOW,
        is_external_output=True,
    )
    registry.register(
        name="open_website",
        handler=lambda url: web.open_website(url),
        schema=OpenWebsiteParams,
        description="Open a website in the default browser.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="docker_list_containers",
        handler=lambda all=False: docker_control.docker_list_containers(all=all),
        schema=DockerListContainersParams,
        description="List running or all Docker containers.",
        risk_tier=RiskTier.LOW,
    )
    registry.register(
        name="docker_start",
        handler=lambda container: docker_control.docker_start(container),
        schema=DockerContainerActionParams,
        description="Start a Docker container.",
        risk_tier=RiskTier.MEDIUM,
    )
    registry.register(
        name="docker_stop",
        handler=lambda container: docker_control.docker_stop(container),
        schema=DockerContainerActionParams,
        description="Stop a running Docker container. Requires approval.",
        risk_tier=RiskTier.HIGH,
    )
    registry.register(
        name="docker_restart",
        handler=lambda container: docker_control.docker_restart(container),
        schema=DockerContainerActionParams,
        description="Restart a Docker container. Requires approval.",
        risk_tier=RiskTier.HIGH,
    )
    registry.register(
        name="get_system_info",
        handler=lambda category="all": windows_control.get_system_info(),
        schema=GetSystemInfoParams,
        description="Get system CPU, RAM, disk, and OS information.",
        risk_tier=RiskTier.LOW,
    )
    def _safe_take_screenshot(save_path=None):
        try:
            from PIL import ImageGrab
            import tempfile
            img = ImageGrab.grab()
            out = save_path or str(Path(tempfile.gettempdir()) / "screenshot.png")
            img.save(out)
            return f"Screenshot saved to: {out}"
        except Exception as e:
            return f"Screenshot error: {e}"

    registry.register(
        name="take_screenshot",
        handler=_safe_take_screenshot,
        schema=TakeScreenshotParams,
        description="Capture full desktop screenshot.",
        risk_tier=RiskTier.LOW,
    )
    registry.register(
        name="open_whatsapp_draft",
        handler=lambda url: BrowserLauncher.open_draft_url(url)[1],
        schema=OpenWhatsAppDraftParams,
        description="Open pre-confirmed WhatsApp draft URL in browser.",
        risk_tier=RiskTier.MEDIUM,
    )

    return registry


# Global defensive registry instance (lazy proxy to eliminate circular imports during plugin initialization)
_global_defensive_registry: Optional[DefensiveToolRegistry] = None


def get_default_defensive_registry() -> DefensiveToolRegistry:
    global _global_defensive_registry
    if _global_defensive_registry is None:
        _global_defensive_registry = create_default_defensive_registry()
    return _global_defensive_registry


class _DefensiveToolRegistryProxy:
    def __getattr__(self, name):
        return getattr(get_default_defensive_registry(), name)

    def __iter__(self):
        return iter(get_default_defensive_registry())

    def __len__(self):
        return len(get_default_defensive_registry())

    def __contains__(self, item):
        return item in get_default_defensive_registry()

    def __repr__(self):
        return repr(get_default_defensive_registry())


defensive_tool_registry = _DefensiveToolRegistryProxy()

