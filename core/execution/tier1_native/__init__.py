# core/execution/tier1_native/__init__.py — Tier 1 Native Windows Adapter
"""
Tier 1 Native Windows Operations Adapter.
Dispatches directly to native_fs, native_process, native_windows, and native_system.
Zero shell invocation, zero command-line string escaping risks.
"""
import logging
import time
from typing import Any, Dict, Optional

from core.execution.execution_context import ExecutionContext
from core.execution.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    TierLevel,
)
from core.execution.tier1_native.filesystem import native_fs
from core.execution.tier1_native.process import native_process
from core.execution.tier1_native.system import native_system
from core.execution.tier1_native.windows import native_windows

logger = logging.getLogger(__name__)


class NativeTier:
    """Tier 1: High-reliability Native Windows Adapter."""

    def __init__(self):
        self.fs = native_fs
        self.process = native_process
        self.windows = native_windows
        self.system = native_system

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """Route tool_name to the appropriate Tier 1 native subsystem."""
        start = time.perf_counter()
        ctx = context or ExecutionContext()
        output: Any = None
        error: Optional[str] = None
        status = ExecutionStatus.SUCCESS

        try:
            # ── File System ──────────────────────────────────────────
            if tool_name == "list_directory":
                res = self.fs.list_directory(path=arguments.get("path", ctx.working_directory))
            elif tool_name == "read_file":
                res = self.fs.read_file(
                    path=arguments.get("path", ""),
                    max_bytes=int(arguments.get("max_bytes", 100_000)),
                )
            elif tool_name == "search_files":
                res = self.fs.search_files(
                    query=arguments.get("query", "*"),
                    directory=arguments.get("directory", ctx.working_directory),
                    max_results=int(arguments.get("max_results", 50)),
                )
            elif tool_name == "get_file_metadata":
                res = self.fs.get_metadata(path=arguments.get("path", ""))
            elif tool_name == "open_folder":
                from tools import windows_control
                res = {"success": True, "message": windows_control.open_folder(arguments.get("path", ctx.working_directory))}
            elif tool_name == "create_directory":
                res = self.fs.create_directory(path=arguments.get("path", ""))
            elif tool_name == "create_file":
                res = self.fs.create_file(
                    path=arguments.get("path", ""),
                    content=arguments.get("content", ""),
                    overwrite=arguments.get("overwrite", True),
                )
            elif tool_name in ("copy_path", "copy_file"):
                res = self.fs.copy_path(
                    source=arguments.get("source", ""),
                    destination=arguments.get("destination", ""),
                )
            elif tool_name in ("move_path", "move_file"):
                res = self.fs.move_path(
                    source=arguments.get("source", ""),
                    destination=arguments.get("destination", ""),
                )
            elif tool_name == "compress_folder":
                res = self.fs.compress_folder(
                    folder_path=arguments.get("folder_path", ""),
                    zip_path=arguments.get("zip_path", ""),
                )
            elif tool_name == "extract_zip":
                res = self.fs.extract_zip(
                    zip_path=arguments.get("zip_path", ""),
                    extract_to=arguments.get("extract_to", ""),
                )
            elif tool_name in ("delete_path", "delete_file", "delete_directory"):
                res = self.fs.delete_path(path=arguments.get("path", ""))
            elif tool_name == "create_office_document":
                from tools import windows_control
                res = {
                    "success": True,
                    "message": windows_control.create_office_document(
                        filename=arguments.get("filename", "document.docx"),
                        content=arguments.get("content", ""),
                        title=arguments.get("title", "Document"),
                        open_after=arguments.get("open_after", True),
                    ),
                }
            elif tool_name == "create_excel_spreadsheet":
                from tools import windows_control
                res = {
                    "success": True,
                    "message": windows_control.create_excel_spreadsheet(
                        filename=arguments.get("filename", "spreadsheet.xlsx"),
                        content=arguments.get("content", ""),
                        title=arguments.get("title", "Sheet"),
                        open_after=arguments.get("open_after", True),
                    ),
                }
            elif tool_name == "create_powerpoint_presentation":
                from tools import windows_control
                res = {
                    "success": True,
                    "message": windows_control.create_powerpoint_presentation(
                        filename=arguments.get("filename", "presentation.pptx"),
                        content=arguments.get("content", ""),
                        title=arguments.get("title", "Presentation"),
                        open_after=arguments.get("open_after", True),
                    ),
                }

            # ── Process & Applications ───────────────────────────────
            elif tool_name == "open_application":
                res = self.process.launch_app(
                    name=arguments.get("name", ""),
                    args=arguments.get("args"),
                )
            elif tool_name == "close_application":
                res = self.process.close_app(
                    name=arguments.get("name", ""),
                    force=arguments.get("force", False),
                )
            elif tool_name == "is_app_running":
                res = self.process.is_app_running(name=arguments.get("name", ""))
            elif tool_name in ("get_process_list", "list_processes"):
                res = self.process.list_processes(
                    limit=int(arguments.get("limit", 50)),
                    sort_by=arguments.get("sort_by", "memory"),
                )
            elif tool_name == "kill_process":
                res = self.process.close_app(
                    name=arguments.get("name", ""),
                    force=True,
                )
            elif tool_name == "list_installed_apps":
                from tools import windows_control
                res = {"success": True, "apps": windows_control.list_installed_apps()}

            # ── Windows Management ───────────────────────────────────
            elif tool_name in ("list_open_windows", "list_windows"):
                res = self.windows.list_windows(query=arguments.get("query"))
            elif tool_name == "get_active_window":
                res = self.windows.get_active_window()
            elif tool_name == "minimize_window":
                res = self.windows.minimize_window(title_or_hwnd=arguments.get("title") or arguments.get("hwnd"))
            elif tool_name == "maximize_window":
                res = self.windows.maximize_window(title_or_hwnd=arguments.get("title") or arguments.get("hwnd"))
            elif tool_name == "restore_window":
                res = self.windows.restore_window(title_or_hwnd=arguments.get("title") or arguments.get("hwnd"))
            elif tool_name == "activate_window":
                res = self.windows.activate_window(title_or_hwnd=arguments.get("title") or arguments.get("hwnd"))
            elif tool_name == "snap_window":
                res = self.windows.snap_window(
                    title_or_hwnd=arguments.get("title") or arguments.get("hwnd"),
                    position=arguments.get("position", "left"),
                )
            elif tool_name == "type_message":
                from tools import windows_control
                msg_out = windows_control.type_message(
                    message=arguments.get("message", ""),
                    app_name_or_title=arguments.get("app_name_or_title", ""),
                    press_enter=arguments.get("press_enter", False),
                )
                res = {"success": not msg_out.startswith("Security Error:"), "message": msg_out}

            # ── System Telemetry & Hardware ──────────────────────────
            elif tool_name == "get_system_info":
                res = self.system.get_system_telemetry(force_refresh=arguments.get("refresh", False))
            elif tool_name == "get_battery_info":
                res = self.system.get_battery_info()
            elif tool_name == "get_wifi_info":
                res = self.system.get_network_info()
            elif tool_name == "get_volume":
                res = self.system.get_volume()
            elif tool_name == "set_volume":
                res = self.system.set_volume(level=int(arguments.get("level", 50)))
            elif tool_name == "get_brightness":
                res = self.system.get_brightness()
            elif tool_name == "set_brightness":
                res = self.system.set_brightness(level=int(arguments.get("level", 50)))
            elif tool_name == "lock_pc":
                res = self.system.lock_pc()
            elif tool_name == "shutdown_pc":
                res = self.system.shutdown_pc(delay_seconds=int(arguments.get("delay_seconds", 30)))
            elif tool_name == "restart_pc":
                res = self.system.restart_pc(delay_seconds=int(arguments.get("delay_seconds", 30)))
            elif tool_name == "cancel_shutdown":
                res = self.system.cancel_shutdown()
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILURE,
                    error=f"Tool '{tool_name}' not implemented in Tier 1 Native adapter.",
                    tier_used=TierLevel.TIER1_NATIVE,
                    tool_name=tool_name,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            # Check outcome
            if isinstance(res, dict) and not res.get("success", True):
                status = ExecutionStatus.FAILURE
                error = res.get("error", "Unknown native error")
                output = res
            else:
                status = ExecutionStatus.SUCCESS
                output = res

        except Exception as e:
            logger.exception(f"Unhandled error in Tier 1 execution for '{tool_name}': {e}")
            status = ExecutionStatus.FAILURE
            error = str(e)

        duration_ms = (time.perf_counter() - start) * 1000
        return ExecutionResult(
            status=status,
            output=output,
            error=error,
            tier_used=TierLevel.TIER1_NATIVE,
            tool_name=tool_name,
            duration_ms=duration_ms,
            verified=(status == ExecutionStatus.SUCCESS),
        )


__all__ = ["NativeTier", "native_fs", "native_process", "native_windows", "native_system"]
