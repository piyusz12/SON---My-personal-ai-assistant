# core/execution/execution_policy.py — Execution Policies and Risk Classifications
"""
Maps tools and operations to risk tiers, execution tiers, timeouts, approval rules,
and verification strategies.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Set

from core.execution.execution_result import TierLevel

# Permission and Risk Tier Constants
READ = "READ"
LOCAL_REVERSIBLE = "LOCAL_REVERSIBLE"
HIGH_IMPACT = "HIGH_IMPACT"
DENIED = "DENIED"

# High-impact operations that strictly require explicit user approval
APPROVAL_REQUIRED_OPERATIONS: Set[str] = {
    "delete_file",
    "delete_directory",
    "delete_path",
    "git_push",
    "git_commit",
    "git_pull",
    "docker_build",
    "pip_install",
    "shutdown_pc",
    "restart_pc",
    "run_tests",
}

# Operations strictly denied by design
DENIED_OPERATIONS: Set[str] = {
    "format_drive",
    "modify_critical_registry",
    "bypass_execution_policy",
    "arbitrary_powershell",
    "arbitrary_bash",
    "elevate_privileges",
    "kill_critical_system_process",
    "raw_disk_write",
}


@dataclass
class OperationPolicy:
    """Policy definition for a specific tool or Windows operation."""
    permission_level: str              # READ, LOCAL_REVERSIBLE, HIGH_IMPACT, DENIED
    preferred_tier: TierLevel          # TIER1_NATIVE, TIER2_SHELL, TIER3_UIA, TIER4_VISUAL
    requires_approval: bool
    timeout_seconds: float
    verification_strategy: str        # e.g., "check_no_error", "check_process_running", etc.
    description: str = ""


# Master Operation Policy Mapping
OPERATION_POLICIES: Dict[str, OperationPolicy] = {
    # ── TIER 1: File System (READ) ──────────────────────────────────
    "list_directory": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 10.0, "check_output_non_empty", "List directory contents"),
    "read_file": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 15.0, "check_output_non_empty", "Read text file contents"),
    "search_files": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 30.0, "check_no_error", "Search files by name pattern"),
    "get_file_metadata": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_output_non_empty", "Get file or folder metadata"),
    "open_folder": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 10.0, "check_no_error", "Open folder in Windows Explorer"),

    # ── TIER 1: File System (LOCAL_REVERSIBLE) ───────────────────────
    "create_directory": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 10.0, "check_path_exists", "Create new directory"),
    "create_file": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 10.0, "check_path_exists", "Create or write file"),
    "copy_path": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 30.0, "check_path_exists", "Copy file or folder"),
    "copy_file": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 30.0, "check_path_exists", "Copy file"),
    "move_path": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 30.0, "check_no_error", "Move or rename file/folder"),
    "move_file": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 30.0, "check_no_error", "Move or rename file"),
    "compress_folder": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 60.0, "check_path_exists", "Compress folder to ZIP archive"),
    "extract_zip": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 60.0, "check_path_exists", "Extract ZIP archive"),
    "create_office_document": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 20.0, "check_path_exists", "Create Word docx document"),
    "create_excel_spreadsheet": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 20.0, "check_path_exists", "Create Excel spreadsheet"),
    "create_powerpoint_presentation": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 20.0, "check_path_exists", "Create PowerPoint presentation"),

    # ── TIER 1: File System (HIGH_IMPACT — requires approval) ────────
    "delete_file": OperationPolicy(HIGH_IMPACT, TierLevel.TIER1_NATIVE, True, 10.0, "check_path_gone", "Permanently delete file"),
    "delete_directory": OperationPolicy(HIGH_IMPACT, TierLevel.TIER1_NATIVE, True, 15.0, "check_path_gone", "Permanently delete folder"),
    "delete_path": OperationPolicy(HIGH_IMPACT, TierLevel.TIER1_NATIVE, True, 15.0, "check_path_gone", "Permanently delete path"),

    # ── TIER 1: Process & Application Management ─────────────────────
    "is_app_running": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Check if application is running"),
    "get_process_list": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 10.0, "check_output_non_empty", "List running processes"),
    "list_processes": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 10.0, "check_output_non_empty", "List running processes"),
    "list_installed_apps": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 15.0, "check_output_non_empty", "List installed applications"),
    "open_application": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 15.0, "check_process_started", "Launch approved application"),
    "close_application": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 10.0, "check_no_error", "Close running application safely"),
    "kill_process": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 10.0, "check_no_error", "Terminate process by name or PID"),

    # ── TIER 1: Window Management ────────────────────────────────────
    "list_open_windows": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_output_non_empty", "List visible desktop windows"),
    "list_windows": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_output_non_empty", "List visible desktop windows"),
    "get_active_window": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Get title and PID of active window"),
    "minimize_window": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Minimize window"),
    "maximize_window": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Maximize window"),
    "restore_window": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Restore window"),
    "activate_window": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Focus / activate window"),
    "snap_window": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Snap window to screen boundary"),
    "type_message": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 10.0, "check_no_error", "Type message into target window"),

    # ── TIER 1: System Monitoring & Hardware ─────────────────────────
    "get_system_info": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 10.0, "check_output_non_empty", "Get CPU, GPU, RAM, disk, battery metrics"),
    "get_battery_info": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_output_non_empty", "Get battery charge level and status"),
    "get_wifi_info": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Get Wi-Fi interface status"),
    "get_volume": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Get system audio volume"),
    "set_volume": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Set system audio volume"),
    "get_brightness": OperationPolicy(READ, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Get display brightness"),
    "set_brightness": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Set display brightness"),
    "lock_pc": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Lock Windows workstation"),
    "shutdown_pc": OperationPolicy(HIGH_IMPACT, TierLevel.TIER1_NATIVE, True, 10.0, "check_no_error", "Schedule PC shutdown"),
    "restart_pc": OperationPolicy(HIGH_IMPACT, TierLevel.TIER1_NATIVE, True, 10.0, "check_no_error", "Schedule PC restart"),
    "cancel_shutdown": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER1_NATIVE, False, 5.0, "check_no_error", "Cancel scheduled shutdown/restart"),

    # ── TIER 2: Git Integration ──────────────────────────────────────
    "git_status": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "Check git working tree status"),
    "git_log": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "Inspect git commit history"),
    "git_diff": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "Inspect git diff"),
    "git_branch": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 10.0, "check_no_error", "List or inspect git branches"),
    "git_remote": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 10.0, "check_no_error", "Inspect git remotes"),
    "git_add": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "Stage files in git"),
    "git_commit": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, True, 20.0, "check_no_error", "Commit staged changes with message"),
    "git_commit_changes": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, True, 20.0, "check_no_error", "Stage and commit changes"),
    "git_pull": OperationPolicy(HIGH_IMPACT, TierLevel.TIER2_SHELL, True, 60.0, "check_no_error", "Pull changes from remote repository"),
    "git_push": OperationPolicy(HIGH_IMPACT, TierLevel.TIER2_SHELL, True, 60.0, "check_no_error", "Push commits to remote repository"),

    # ── TIER 2: Docker Integration ───────────────────────────────────
    "docker_list_containers": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "List Docker containers"),
    "docker_list_images": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "List Docker images"),
    "docker_inspect_container": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 10.0, "check_no_error", "Inspect Docker container details"),
    "docker_logs": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 15.0, "check_no_error", "Get recent Docker container logs"),
    "docker_check_status": OperationPolicy(READ, TierLevel.TIER2_SHELL, False, 10.0, "check_no_error", "Check Docker daemon status"),
    "docker_start": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Start Docker container"),
    "docker_start_container": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Start Docker container"),
    "docker_stop": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Stop Docker container"),
    "docker_stop_container": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Stop Docker container"),
    "docker_restart": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Restart Docker container"),
    "docker_restart_container": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 30.0, "check_no_error", "Restart Docker container"),
    "docker_build": OperationPolicy(HIGH_IMPACT, TierLevel.TIER2_SHELL, True, 300.0, "check_no_error", "Build Docker image from Dockerfile"),

    # ── TIER 2: VS Code & Development Environment ────────────────────
    "open_vscode": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 15.0, "check_process_started", "Open VS Code"),
    "open_vscode_project": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 15.0, "check_process_started", "Open project in VS Code"),
    "create_venv": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, False, 60.0, "check_path_exists", "Create Python virtual environment"),
    "install_requirements": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, True, 180.0, "check_no_error", "Install requirements.txt in venv"),
    "pip_install": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER2_SHELL, True, 180.0, "check_no_error", "Install Python packages"),
    "run_tests": OperationPolicy(HIGH_IMPACT, TierLevel.TIER2_SHELL, True, 180.0, "check_no_error", "Run test suite (pytest)"),

    # ── TIER 3 & 4 (Future Phase Stubs) ──────────────────────────────
    "click_ui_element": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER3_UIA, False, 10.0, "check_no_error", "Click UI element via UIA"),
    "find_ui_element": OperationPolicy(READ, TierLevel.TIER3_UIA, False, 10.0, "check_no_error", "Find UI element via UIA"),
    "visual_identify": OperationPolicy(READ, TierLevel.TIER4_VISUAL, False, 10.0, "check_no_error", "Identify visual screen element"),
    "visual_click": OperationPolicy(LOCAL_REVERSIBLE, TierLevel.TIER4_VISUAL, False, 10.0, "check_no_error", "Click screen coordinate via vision"),
}


def get_policy(tool_name: str) -> OperationPolicy:
    """Retrieve the policy for a tool, falling back to a safe default if unknown."""
    if tool_name in DENIED_OPERATIONS:
        return OperationPolicy(
            permission_level=DENIED,
            preferred_tier=TierLevel.TIER1_NATIVE,
            requires_approval=False,
            timeout_seconds=0.0,
            verification_strategy="blocked",
            description=f"Denied operation: {tool_name}",
        )

    if tool_name in OPERATION_POLICIES:
        return OPERATION_POLICIES[tool_name]

    # Default policy for unmapped operations: safe READ, native tier, 30s timeout
    return OperationPolicy(
        permission_level=READ,
        preferred_tier=TierLevel.TIER1_NATIVE,
        requires_approval=False,
        timeout_seconds=30.0,
        verification_strategy="check_no_error",
        description=f"Generic tool: {tool_name}",
    )
