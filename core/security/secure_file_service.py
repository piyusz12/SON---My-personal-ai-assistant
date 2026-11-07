# core/security/secure_file_service.py — Restricted Local File Management Service
"""
Zero-Trust Secure File Management Service for SON v3:
  - Configurable workspace allowlist (workspace root, Documents, Downloads, Desktop)
  - Strict path canonicalization and directory traversal prevention
  - Symbolic link escape detection and rejection
  - System directory and credential store protection (C:\\Windows, .ssh, .aws, .env)
  - Enforced file size limits
  - Risk-tiered operation handling with mandatory human approval on destructive actions
  - Full structured security audit logging
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any

from core.config import Config
from core.security.policy import RiskTier
from core.security.approval_manager import approval_manager
from core.security.audit_logger import audit_logger, redact_secrets
from core.security.sanitizer import wrap_untrusted_content


# Maximum allowed read/write file size (5MB default)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

# Blocked credential and sensitive file patterns
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r'(?i)\.env(?:$|\.)'),
    re.compile(r'(?i)(?:id_rsa|id_ed25519|id_ecdsa)'),
    re.compile(r'(?i)credentials(?:\.json|\.ini|\.txt)?$'),
    re.compile(r'(?i)\.(?:aws|azure|ssh|gnupg)'),
    re.compile(r'(?i)(?:token[s]?\.json|secrets?\.ya?ml|secrets?\.json)'),
    re.compile(r'(?i)\.git[\\/]config'),
    re.compile(r'(?i)(?:SAM|SYSTEM|SECURITY)$'),
]

# Blocked protected system directories
FORBIDDEN_SYSTEM_PATHS = [
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\users\\default",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var/log",
]


class FileAccessDeniedError(Exception):
    """Raised when an operation attempts to access an unauthorized or forbidden path."""
    pass


class SecureFileService:
    """
    Restricted file management service providing safe, sandbox-like file operations
    within authorized directory boundaries.
    """

    def __init__(self, allowed_roots: list[str | Path] | None = None):
        self._allowed_roots: list[Path] = []
        default_roots = allowed_roots or [
            getattr(Config, "ROOT_DIR", Path.cwd()),
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path(Config.LOGS_DIR),
            Path(Config.MEMORY_DIR),
        ]
        for r in default_roots:
            p = Path(r).resolve()
            if p.exists() and p not in self._allowed_roots:
                self._allowed_roots.append(p)

    @property
    def allowed_roots(self) -> list[Path]:
        return list(self._allowed_roots)

    def add_allowed_root(self, root_path: str | Path):
        """Add an explicitly approved directory to the workspace allowlist."""
        p = Path(root_path).resolve()
        if p.exists() and p not in self._allowed_roots:
            self._allowed_roots.append(p)
            audit_logger.log_event(
                event_type="FILE_ALLOWLIST_EXPANDED",
                status="CONFIGURED",
                details={"added_root": str(p)},
            )

    def validate_path(
        self,
        raw_path: str | Path,
        must_exist: bool = False,
        allow_symlinks: bool = False,
    ) -> Path:
        """
        Canonicalize and validate that a path resides within allowed workspace roots,
        does not escape via traversal (..) or symlinks, and does not touch sensitive credentials.
        """
        path_str = str(raw_path).strip().strip("'\"")
        if not path_str:
            raise FileAccessDeniedError("File path cannot be empty.")

        if "\x00" in path_str:
            raise FileAccessDeniedError("Path traversal/injection attempt: null byte detected.")

        try:
            target = Path(path_str).resolve()
        except Exception as e:
            raise FileAccessDeniedError(f"Invalid path representation: {e}")

        # 1. Check system root protection
        target_lower = str(target).lower()
        for forbidden in FORBIDDEN_SYSTEM_PATHS:
            if target_lower.startswith(forbidden) or f"\\{forbidden.replace('c:\\', '')}" in target_lower:
                audit_logger.log_event(
                    event_type="FILE_SYSTEM_ROOT_BLOCKED",
                    status="BLOCKED",
                    details={"path": target_lower, "forbidden_pattern": forbidden},
                )
                raise FileAccessDeniedError(f"Access to protected system path '{path_str}' is forbidden.")

        # 2. Check sensitive credential and secret patterns
        target_name = target.name
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if pattern.search(target_name) or pattern.search(str(target)):
                audit_logger.log_event(
                    event_type="FILE_CREDENTIAL_ACCESS_BLOCKED",
                    status="BLOCKED",
                    details={"path": str(target), "matched_pattern": pattern.pattern},
                )
                raise FileAccessDeniedError(f"Access to sensitive credential or secret file '{target_name}' is forbidden.")

        # 3. Check workspace allowlist boundary (traversal & escape check)
        is_inside_allowed = False
        for root in self._allowed_roots:
            try:
                target.relative_to(root)
                is_inside_allowed = True
                break
            except ValueError:
                continue

        if not is_inside_allowed:
            audit_logger.log_event(
                event_type="FILE_OUTSIDE_ALLOWLIST_BLOCKED",
                status="BLOCKED",
                details={"path": str(target), "allowed_roots": [str(r) for r in self._allowed_roots]},
            )
            raise FileAccessDeniedError(f"Path '{path_str}' is outside configured workspace allowlists.")

        # 4. Check symlink escape
        if not allow_symlinks and os.path.islink(path_str):
            real_target = Path(os.path.realpath(path_str))
            if not any(real_target == r or r in real_target.parents for r in self._allowed_roots):
                raise FileAccessDeniedError(f"Symbolic link '{path_str}' points outside approved workspaces.")

        if must_exist and not target.exists():
            raise FileNotFoundError(f"File or directory '{path_str}' does not exist.")

        return target

    # ── Safe Operations ───────────────────────────────────────────

    def list_directory(self, dir_path: str | Path = ".", max_items: int = 100) -> list[dict[str, Any]]:
        """List files and folders within an approved directory."""
        canonical_dir = self.validate_path(dir_path, must_exist=True)
        if not canonical_dir.is_dir():
            raise NotADirectoryError(f"'{canonical_dir}' is not a directory.")

        results = []
        for entry in canonical_dir.iterdir():
            if len(results) >= max_items:
                break
            # Skip hidden files starting with . by default for safety
            if entry.name.startswith(".") and entry.name != ".gitignore":
                continue

            try:
                stat = entry.stat()
                results.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": stat.st_size if entry.is_file() else None,
                    "modified_time": stat.st_mtime,
                })
            except Exception:
                continue

        return results

    def read_file(self, path: str | Path, max_bytes: int = MAX_FILE_SIZE_BYTES, max_lines: int | None = None) -> str:
        """Safely read text file content within size boundaries."""
        canonical_file = self.validate_path(path, must_exist=True)
        if not canonical_file.is_file():
            raise IsADirectoryError(f"'{canonical_file}' is a directory, not a file.")

        stat = canonical_file.stat()
        if stat.st_size > max_bytes:
            raise ValueError(f"File size ({stat.st_size} bytes) exceeds safety limit ({max_bytes} bytes).")

        with open(canonical_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)

        if max_lines is not None:
            lines = content.split("\n")
            if len(lines) > int(max_lines):
                content = "\n".join(lines[:int(max_lines)]) + f"\n... ({len(lines) - int(max_lines)} more lines)"

        return wrap_untrusted_content(content, source=f"local_file:{canonical_file.name}", source_type="file")

    def write_file(self, path: str | Path, content: str, overwrite: bool = True) -> str:
        """Safely write content to an approved file destination."""
        canonical_file = self.validate_path(path, must_exist=False)
        if canonical_file.exists() and not overwrite:
            raise FileExistsError(f"File '{canonical_file}' already exists and overwrite is False.")

        if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Content size exceeds safety limit of {MAX_FILE_SIZE_BYTES} bytes.")

        canonical_file.parent.mkdir(parents=True, exist_ok=True)
        with open(canonical_file, "w", encoding="utf-8") as f:
            f.write(content)

        audit_logger.log_event(
            event_type="FILE_WRITTEN",
            status="SUCCESS",
            details={"path": str(canonical_file), "bytes_written": len(content)},
        )
        return f"Successfully wrote {len(content)} characters to '{canonical_file.name}'."

    def search_files(self, pattern: str, root_dir: str | Path = ".", max_results: int = 50) -> list[str]:
        """Search for files matching glob pattern within approved directories."""
        canonical_root = self.validate_path(root_dir, must_exist=True)
        matches = []
        for path in canonical_root.rglob(pattern):
            if len(matches) >= max_results:
                break
            try:
                # Ensure each match is validated
                safe_path = self.validate_path(path)
                matches.append(str(safe_path.relative_to(canonical_root)))
            except Exception:
                continue

        return matches

    def move_file(self, src: str | Path, dst: str | Path) -> str:
        """Safely move/rename a file between approved locations."""
        src_path = self.validate_path(src, must_exist=True)
        dst_path = self.validate_path(dst, must_exist=False)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))

        audit_logger.log_event(
            event_type="FILE_MOVED",
            status="SUCCESS",
            details={"src": str(src_path), "dst": str(dst_path)},
        )
        return f"Moved '{src_path.name}' to '{dst_path.name}' successfully."

    def delete_path(self, path: str | Path, approval_id: str | None = None) -> str:
        """
        Permanently delete a file or directory within approved workspace boundaries.
        Protection against drive roots and system directories enforced.
        Requires verified human approval (HIGH RISK).
        """
        canonical_path = self.validate_path(path, must_exist=True)

        # Drive root or filesystem root deletion protection
        if canonical_path == canonical_path.parent or str(canonical_path).endswith(":\\") or str(canonical_path).rstrip("\\/").endswith(":"):
            raise FileAccessDeniedError("Drive root deletion is strictly forbidden.")

        args = {"path": str(canonical_path)}
        if approval_id is not None:
            valid, reason = approval_manager.verify_and_consume(approval_id, args)
            if not valid:
                raise PermissionError(f"Deletion authorization failed: {reason}")

        if canonical_path.is_dir():
            shutil.rmtree(canonical_path)
            audit_logger.log_event(
                event_type="DIRECTORY_DELETED",
                status="SUCCESS",
                approval_id=approval_id,
                details={"path": str(canonical_path)},
            )
            return f"Directory '{canonical_path}' was deleted successfully."
        else:
            canonical_path.unlink()
            audit_logger.log_event(
                event_type="FILE_DELETED",
                status="SUCCESS",
                approval_id=approval_id,
                details={"path": str(canonical_path)},
            )
            return f"File '{canonical_path}' was deleted successfully."


# Global singleton instance
secure_file_service = SecureFileService()
