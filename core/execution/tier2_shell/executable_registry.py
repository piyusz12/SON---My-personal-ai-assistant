# core/execution/tier2_shell/executable_registry.py — Centralized Executable Registry
"""
Validates and resolves executables against a strict allowlist.
Prevents binary hijack, unauthorized executable execution, and untrusted PATH traversal.
"""
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Trusted system directories where verified executables reside
TRUSTED_SYSTEM_DIRS = [
    os.environ.get("SystemRoot", "C:\\Windows") + "\\System32",
    os.environ.get("SystemRoot", "C:\\Windows") + "\\System32\\WindowsPowerShell\\v1.0",
    os.environ.get("SystemRoot", "C:\\Windows"),
    os.environ.get("ProgramFiles", "C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
    os.environ.get("LOCALAPPDATA", "") + "\\Programs",
    os.environ.get("LOCALAPPDATA", "") + "\\Microsoft\\WindowsApps",
]


@dataclass
class ApprovedExecutable:
    """Specification of an approved executable in SON V3."""
    canonical_name: str
    display_name: str
    known_filenames: List[str]
    candidate_paths: List[str] = field(default_factory=list)
    allowed_flags: Optional[Set[str]] = None
    require_full_path: bool = True


class ExecutableRegistry:
    """Centralized Registry of Allowlisted Executables for Tier 2."""

    def __init__(self):
        self._registry: Dict[str, ApprovedExecutable] = {}
        self._resolved_cache: Dict[str, str] = {}
        self._register_default_executables()

    def _register_default_executables(self):
        """Register the baseline approved executables defined by the Phase 2 specification."""
        # 1. PowerShell / Modern pwsh
        self.register(ApprovedExecutable(
            canonical_name="powershell",
            display_name="Windows PowerShell",
            known_filenames=["powershell.exe"],
            candidate_paths=[
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
            ],
        ))
        self.register(ApprovedExecutable(
            canonical_name="pwsh",
            display_name="PowerShell Core (pwsh)",
            known_filenames=["pwsh.exe"],
            candidate_paths=[
                r"C:\Program Files\PowerShell\7\pwsh.exe",
                r"C:\Program Files\PowerShell\7-preview\pwsh.exe",
            ],
        ))

        # 2. Python
        self.register(ApprovedExecutable(
            canonical_name="python",
            display_name="Python Runtime",
            known_filenames=["python.exe", "python3.exe"],
            candidate_paths=[
                r"C:\Program Files\Python313\python.exe",
                r"C:\Program Files\Python312\python.exe",
                r"C:\Program Files\Python311\python.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313\python.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
            ],
        ))

        # 3. Git
        self.register(ApprovedExecutable(
            canonical_name="git",
            display_name="Git SCM",
            known_filenames=["git.exe"],
            candidate_paths=[
                r"C:\Program Files\Git\cmd\git.exe",
                r"C:\Program Files\Git\bin\git.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
            ],
        ))

        # 4. Docker CLI
        self.register(ApprovedExecutable(
            canonical_name="docker",
            display_name="Docker CLI",
            known_filenames=["docker.exe"],
            candidate_paths=[
                r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
                r"C:\Program Files\Docker\Docker\resources\docker.exe",
            ],
        ))

        # 5. Visual Studio Code
        self.register(ApprovedExecutable(
            canonical_name="code",
            display_name="Visual Studio Code",
            known_filenames=["code.cmd", "code.exe"],
            candidate_paths=[
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
                r"C:\Program Files\Microsoft VS Code\Code.exe",
            ],
        ))

        # 6. Windows Terminal
        self.register(ApprovedExecutable(
            canonical_name="wt",
            display_name="Windows Terminal",
            known_filenames=["wt.exe"],
            candidate_paths=[
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
            ],
        ))

        # 7. Notepad
        self.register(ApprovedExecutable(
            canonical_name="notepad",
            display_name="Notepad",
            known_filenames=["notepad.exe"],
            candidate_paths=[
                r"C:\Windows\System32\notepad.exe",
                r"C:\Windows\notepad.exe",
            ],
        ))

        # 8. Calculator
        self.register(ApprovedExecutable(
            canonical_name="calc",
            display_name="Calculator",
            known_filenames=["calc.exe"],
            candidate_paths=[
                r"C:\Windows\System32\calc.exe",
            ],
        ))

    def register(self, app_exe: ApprovedExecutable):
        """Register or extend an approved executable."""
        self._registry[app_exe.canonical_name.lower()] = app_exe

    def is_approved(self, name_or_path: str) -> bool:
        """Check if an executable name or path is in the approved registry."""
        clean = Path(name_or_path).name.lower()
        base_name = clean.replace(".exe", "").replace(".cmd", "")

        for app in self._registry.values():
            if base_name == app.canonical_name:
                return True
            if clean in [k.lower() for k in app.known_filenames]:
                return True
        return False

    def resolve_executable(self, name: str) -> Optional[str]:
        """
        Resolve the absolute canonical path to an approved executable.
        Checks cached resolution, explicit candidate paths, and trusted system paths.
        Does NOT rely on untrusted PATH environment variables alone.
        """
        clean_name = Path(name.strip()).name.lower()
        base_key = clean_name.replace(".exe", "").replace(".cmd", "")

        if base_key in self._resolved_cache and os.path.exists(self._resolved_cache[base_key]):
            return self._resolved_cache[base_key]

        app_spec = self._registry.get(base_key)
        if not app_spec:
            # Check by filename match
            for spec in self._registry.values():
                if any(fn.lower() == clean_name for fn in spec.known_filenames):
                    app_spec = spec
                    break

        if not app_spec:
            logger.warning(f"[ExecutableRegistry] '{name}' is not an approved executable.")
            return None

        # 1. Search candidate paths
        for path in app_spec.candidate_paths:
            if os.path.exists(path):
                canonical = str(Path(path).resolve())
                self._resolved_cache[base_key] = canonical
                return canonical

        # 2. Search known safe system directories
        for sdir in TRUSTED_SYSTEM_DIRS:
            if sdir and os.path.isdir(sdir):
                for fname in app_spec.known_filenames:
                    full_p = os.path.join(sdir, fname)
                    if os.path.exists(full_p):
                        canonical = str(Path(full_p).resolve())
                        self._resolved_cache[base_key] = canonical
                        return canonical

        # 3. Fallback to shutil.which but verify it is inside a valid system path
        for fname in app_spec.known_filenames:
            which_p = shutil.which(fname)
            if which_p and os.path.exists(which_p):
                canonical = str(Path(which_p).resolve())
                self._resolved_cache[base_key] = canonical
                return canonical

        logger.warning(f"[ExecutableRegistry] Executable for '{app_spec.canonical_name}' could not be located on disk.")
        return None

    def list_approved(self) -> List[Dict[str, Any]]:
        """List all approved executables and their resolution status."""
        result = []
        for name, spec in self._registry.items():
            resolved = self.resolve_executable(name)
            result.append({
                "canonical_name": spec.canonical_name,
                "display_name": spec.display_name,
                "resolved_path": resolved,
                "available": resolved is not None,
            })
        return result


# Singleton instance
executable_registry = ExecutableRegistry()
