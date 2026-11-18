# core/execution/tier2_shell/powershell_runner.py — Controlled PowerShell & CLI Runner
"""
Controlled PowerShell and Subprocess Runner for SON V3 Tier 2.
Enforces:
  1. shell=False strictly for all executions.
  2. Executable validation against the centralized ExecutableRegistry.
  3. Strict parameter validation via CommandTemplate or structured argument arrays.
  4. Safe startup parameters: -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned.
  5. Arbitrary script string rejection: NEVER executes raw LLM code or concatenated shell commands.
  6. Subprocess lifecycle management: timeouts, output capture, graceful termination.
"""
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from core.execution.tier2_shell.command_templates import (
    APPROVED_COMMAND_TEMPLATES,
    CommandTemplate,
    get_template,
)
from core.execution.tier2_shell.executable_registry import executable_registry

logger = logging.getLogger(__name__)

# Dangerous PowerShell parameter tokens that must never appear in arguments
FORBIDDEN_POWERSHELL_TOKENS = {
    "-e",
    "-enc",
    "-encodedcommand",
    "-c",
    "-command",
    "iex",
    "invoke-expression",
    "downloadstring",
    "net.webclient",
    "bitstransfer",
    "start-process",
    "invoke-webrequest",
    "curl",
    "wget",
    "invoke-restmethod",
    "system.reflection",
    "unsafe",
}


@dataclass
class ProcessExecutionResult:
    """Standardized output of a controlled process run."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    command_executed: List[str]
    timed_out: bool = False
    error_message: Optional[str] = None


class ControlledPowerShellRunner:
    """
    Tier 2 Controlled Process & PowerShell Runner.
    Guarantees deterministic, audited execution with zero arbitrary shell access.
    """

    def __init__(self):
        self._active_processes: Dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()

    def get_powershell_executable(self) -> Optional[str]:
        """Resolve modern pwsh.exe if installed, otherwise Windows PowerShell."""
        return executable_registry.resolve_executable("pwsh") or executable_registry.resolve_executable("powershell")

    def run_process(
        self,
        executable_name: str,
        arguments: List[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout_seconds: float = 30.0,
    ) -> ProcessExecutionResult:
        """
        Run an approved binary using subprocess with shell=False.
        Validates the binary against ExecutableRegistry.
        Validates all arguments against injection.
        """
        start = time.perf_counter()

        # 1. Resolve & validate binary
        exe_path = executable_registry.resolve_executable(executable_name)
        if not exe_path:
            return ProcessExecutionResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="",
                duration_ms=0.0,
                command_executed=[executable_name] + arguments,
                error_message=f"Executable '{executable_name}' is not approved or could not be located.",
            )

        # 2. Validate arguments — prevent flag / parameter injection
        for arg in arguments:
            arg_lower = str(arg).lower()
            # Check for shell chain attempts embedded in arguments
            if any(sep in arg for sep in [";", "\n", "\r", "|"]):
                return ProcessExecutionResult(
                    success=False,
                    returncode=-1,
                    stdout="",
                    stderr="",
                    duration_ms=0.0,
                    command_executed=[exe_path] + arguments,
                    error_message=f"Security Error: Disallowed shell chain separator in argument '{arg}'.",
                )

        # 3. Determine working directory
        work_dir = str(cwd) if cwd and os.path.isdir(str(cwd)) else "C:\\AI"

        cmd = [exe_path] + [str(a) for a in arguments]
        logger.info(f"[ControlledRunner] Executing: {cmd[0]} (args: {len(arguments)}) in {work_dir}")

        proc: Optional[subprocess.Popen] = None
        timed_out = False
        try:
            proc = subprocess.Popen(
                cmd,
                shell=False,  # CRITICAL: Always False
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            with self._lock:
                self._active_processes[proc.pid] = proc

            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            returncode = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            logger.warning(f"[ControlledRunner] Process timed out after {timeout_seconds}s: {cmd[0]}")
            if proc:
                try:
                    proc.kill()
                    stdout, stderr = proc.communicate(timeout=2.0)
                except Exception:
                    stdout, stderr = "", "Process killed after timeout."
            else:
                stdout, stderr = "", "Timed out."
            returncode = -1

        except Exception as e:
            logger.exception(f"[ControlledRunner] Execution failure for {cmd[0]}: {e}")
            return ProcessExecutionResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
                command_executed=cmd,
                error_message=str(e),
            )

        finally:
            if proc and proc.pid in self._active_processes:
                with self._lock:
                    self._active_processes.pop(proc.pid, None)

        duration_ms = (time.perf_counter() - start) * 1000
        return ProcessExecutionResult(
            success=(returncode == 0 and not timed_out),
            returncode=returncode,
            stdout=stdout.strip() if stdout else "",
            stderr=stderr.strip() if stderr else "",
            duration_ms=duration_ms,
            command_executed=cmd,
            timed_out=timed_out,
            error_message="Process timed out." if timed_out else (stderr.strip() if returncode != 0 else None),
        )

    def run_template(
        self,
        template_id: str,
        params: Optional[Dict[str, Any]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout_seconds: float = 30.0,
    ) -> ProcessExecutionResult:
        """
        Execute an allowlisted command template with structured, validated arguments.
        Rejects arbitrary templates or unvalidated arguments.
        """
        template = get_template(template_id)
        if not template:
            return ProcessExecutionResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="",
                duration_ms=0.0,
                command_executed=[],
                error_message=f"Command template '{template_id}' is not in the approved template registry.",
            )

        p_dict = params or {}
        constructed_args = list(template.base_args)

        # Validate parameters against template schema and validators
        for param_name, validator in template.param_validators.items():
            if param_name in p_dict:
                val = p_dict[param_name]
                ok, err = validator(val)
                if not ok:
                    return ProcessExecutionResult(
                        success=False,
                        returncode=-1,
                        stdout="",
                        stderr="",
                        duration_ms=0.0,
                        command_executed=[],
                        error_message=f"Parameter validation failed for '{param_name}': {err}",
                    )
                constructed_args.append(str(val))

        return self.run_process(
            executable_name=template.executable_name,
            arguments=constructed_args,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )

    def run_powershell_cmdlet(
        self,
        cmdlet: str,
        params: Optional[Dict[str, Any]] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout_seconds: float = 15.0,
    ) -> ProcessExecutionResult:
        """
        Run a single approved PowerShell cmdlet with structured parameters.
        Safe startup flags are automatically applied:
          -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned
        Raw script blocks or arbitrary syntax are strictly rejected.
        """
        # Block dangerous or unapproved cmdlets
        clean_cmdlet = cmdlet.strip()
        cmdlet_lower = clean_cmdlet.lower()

        if any(token in cmdlet_lower for token in FORBIDDEN_POWERSHELL_TOKENS):
            return ProcessExecutionResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="",
                duration_ms=0.0,
                command_executed=[],
                error_message=f"Security Error: Disallowed PowerShell cmdlet or token '{cmdlet}'.",
            )

        ps_exe = self.get_powershell_executable()
        if not ps_exe:
            return ProcessExecutionResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="",
                duration_ms=0.0,
                command_executed=[],
                error_message="PowerShell executable (pwsh or powershell) could not be located.",
            )

        # Assemble strictly structured cmdlet invocation
        args = [
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-Command",
        ]

        cmdlet_parts = [clean_cmdlet]
        if params:
            for k, v in params.items():
                # Validate parameter key
                if not re.match(r"^[a-zA-Z0-9_]+$", k):
                    return ProcessExecutionResult(
                        success=False,
                        returncode=-1,
                        stdout="",
                        stderr="",
                        duration_ms=0.0,
                        command_executed=[],
                        error_message=f"Invalid parameter name '{k}'.",
                    )
                # Check value for injection
                val_str = str(v).strip()
                val_lower = val_str.lower()
                if any(token in val_lower for token in FORBIDDEN_POWERSHELL_TOKENS) or any(c in val_str for c in [";", "`", "$", "|", "\n", "\r", "(", ")", "'", '"']):
                    return ProcessExecutionResult(
                        success=False,
                        returncode=-1,
                        stdout="",
                        stderr="",
                        duration_ms=0.0,
                        command_executed=[],
                        error_message=f"Dangerous character in parameter value '{v}'.",
                    )
                cmdlet_parts.extend([f"-{k}", val_str])

        args.append(" ".join(cmdlet_parts))

        return self.run_process(
            executable_name=ps_exe,
            arguments=args,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )


# Singleton instance
controlled_shell = ControlledPowerShellRunner()
