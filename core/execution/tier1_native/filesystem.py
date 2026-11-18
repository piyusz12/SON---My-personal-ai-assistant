# core/execution/tier1_native/filesystem.py — Tier 1 Native File System Operations
"""
Deterministic, permission-controlled, path-validated file system operations.
Uses pathlib, os, shutil, zipfile with strict canonical path validation and traversal guards.
"""
from datetime import datetime
import fnmatch
import logging
import os
from pathlib import Path
import shutil
import zipfile
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# System directories strictly protected from modification or deletion
PROTECTED_SYSTEM_ROOTS = [
    os.environ.get("SystemRoot", "C:\\Windows"),
    os.environ.get("ProgramFiles", "C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
]

# Sensitive user root paths that should never be deleted
SYSTEM_DRIVE = os.environ.get("SystemDrive", "C:")


class NativeFileSystem:
    """Tier 1 File System Engine with canonical path security."""

    @staticmethod
    def canonicalize(path: Union[str, Path]) -> Path:
        """Resolve to canonical absolute path, resolving symlinks and normalising slashes."""
        p_str = str(path).strip()
        # Normalize bare drive like 'C:' to 'C:\' so it points to the drive root
        if len(p_str) == 2 and p_str[1] == ":" and p_str[0].isalpha():
            p_str += "\\"
        p = Path(p_str).expanduser()
        return p.resolve()

    @classmethod
    def is_protected_path(cls, path: Union[str, Path]) -> tuple[bool, str]:
        """
        Verify if a path target points to a protected system area, drive root, or sensitive directory.
        Returns (is_protected, reason).
        """
        try:
            resolved = cls.canonicalize(path)
            resolved_str = str(resolved).lower()

            # 1. Drive roots (e.g. C:\, D:\)
            if resolved == resolved.anchor or resolved_str.endswith(":\\") or resolved_str.rstrip("\\/").endswith(":"):
                return True, f"Operation on drive root '{resolved}' is strictly prohibited."

            # 2. Operating system directories (C:\Windows, C:\Program Files, etc.)
            for sys_root in PROTECTED_SYSTEM_ROOTS:
                if sys_root:
                    p_sys = Path(sys_root).resolve()
                    if resolved == p_sys or resolved.is_relative_to(p_sys):
                        return True, f"Target path '{resolved}' is inside protected system directory '{p_sys}'."

            # 3. Users root directory itself (e.g. C:\Users)
            users_root = Path(SYSTEM_DRIVE + "\\Users").resolve()
            if resolved == users_root:
                return True, "Operation on 'C:\\Users' root directory is prohibited."

            # 4. Critical system user profiles
            for default_profile in ["default", "public", "all users", "default user"]:
                prof_path = users_root / default_profile
                if resolved == prof_path or resolved.is_relative_to(prof_path):
                    return True, f"Target path '{resolved}' is inside protected user profile '{default_profile}'."

            return False, ""
        except Exception as e:
            return True, f"Failed to validate path security: {e}"

    @classmethod
    def validate_traversal(cls, base_dir: Union[str, Path], target_path: Union[str, Path]) -> tuple[bool, str]:
        """Ensure target_path does not escape base_dir via symlinks or '..'."""
        try:
            base = cls.canonicalize(base_dir)
            target = cls.canonicalize(target_path)
            if not target.is_relative_to(base):
                return False, f"Path traversal detected: '{target}' escapes base directory '{base}'."
            return True, ""
        except Exception as e:
            return False, f"Traversal validation error: {e}"

    # ── READ Operations ─────────────────────────────────────────────

    def list_directory(self, path: Union[str, Path] = "C:\\AI") -> Dict[str, Any]:
        """List files and folders in directory with metadata."""
        target = self.canonicalize(path)
        if not target.exists():
            return {"success": False, "error": f"Directory not found: '{path}'"}
        if not target.is_dir():
            return {"success": False, "error": f"Path is not a directory: '{path}'"}

        entries = []
        try:
            with os.scandir(target) as it:
                for entry in it:
                    try:
                        stat = entry.stat()
                        entries.append({
                            "name": entry.name,
                            "is_dir": entry.is_dir(),
                            "is_file": entry.is_file(),
                            "is_symlink": entry.is_symlink(),
                            "size_bytes": stat.st_size if entry.is_file() else 0,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        })
                    except (PermissionError, FileNotFoundError):
                        continue
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return {
                "success": True,
                "path": str(target),
                "count": len(entries),
                "entries": entries,
            }
        except PermissionError:
            return {"success": False, "error": f"Permission denied accessing directory: '{path}'"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, path: Union[str, Path], max_bytes: int = 100_000, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read text file with byte limit to prevent memory exhaustion."""
        target = self.canonicalize(path)
        if not target.exists():
            return {"success": False, "error": f"File not found: '{path}'"}
        if not target.is_file():
            return {"success": False, "error": f"Path is not a regular file: '{path}'"}

        try:
            size = target.stat().st_size
            with open(target, "r", encoding=encoding, errors="replace") as f:
                content = f.read(max_bytes)
            truncated = size > max_bytes
            return {
                "success": True,
                "path": str(target),
                "content": content,
                "size_bytes": size,
                "truncated": truncated,
            }
        except PermissionError:
            return {"success": False, "error": f"Permission denied reading file: '{path}'"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(
        self,
        query: str,
        directory: Union[str, Path] = "C:\\AI",
        max_results: int = 50,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """Search files matching wildcard pattern."""
        root = self.canonicalize(directory)
        if not root.exists() or not root.is_dir():
            return {"success": False, "error": f"Search directory does not exist: '{directory}'"}

        pattern = query if ("*" in query or "?" in query) else f"*{query}*"
        matches = []

        try:
            if recursive:
                for dirpath, dirnames, filenames in os.walk(root):
                    # Skip common noisy or vendor directories
                    dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".venv", "__pycache__", "$RECYCLE.BIN")]
                    for fname in filenames:
                        if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                            full_p = Path(dirpath) / fname
                            matches.append(str(full_p))
                            if len(matches) >= max_results:
                                break
                    if len(matches) >= max_results:
                        break
            else:
                for entry in root.glob(pattern):
                    if entry.is_file():
                        matches.append(str(entry))
                        if len(matches) >= max_results:
                            break

            return {
                "success": True,
                "query": query,
                "root": str(root),
                "count": len(matches),
                "results": matches,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_metadata(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Get detailed metadata for file or directory."""
        target = self.canonicalize(path)
        if not target.exists():
            return {"success": False, "error": f"Path not found: '{path}'"}

        try:
            stat = target.stat()
            return {
                "success": True,
                "path": str(target),
                "name": target.name,
                "is_dir": target.is_dir(),
                "is_file": target.is_file(),
                "is_symlink": target.is_symlink(),
                "size_bytes": stat.st_size if target.is_file() else self._get_dir_size(target),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, FileNotFoundError):
                        pass
        except Exception:
            pass
        return total

    # ── MUTATION Operations ─────────────────────────────────────────

    def create_directory(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Create directory recursively."""
        target = self.canonicalize(path)
        is_prot, reason = self.is_protected_path(target)
        if is_prot:
            return {"success": False, "error": f"Cannot create directory: {reason}"}

        try:
            target.mkdir(parents=True, exist_ok=True)
            return {"success": True, "path": str(target), "message": f"Created directory '{target}'."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_file(self, path: Union[str, Path], content: str = "", overwrite: bool = True) -> Dict[str, Any]:
        """Create or write to a text file."""
        target = self.canonicalize(path)
        is_prot, reason = self.is_protected_path(target)
        if is_prot:
            return {"success": False, "error": f"Cannot write file: {reason}"}

        if target.exists() and not overwrite:
            return {"success": False, "error": f"File '{target}' already exists and overwrite is False."}

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(target),
                "bytes_written": len(content.encode("utf-8")),
                "message": f"Successfully wrote file '{target.name}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_path(self, source: Union[str, Path], destination: Union[str, Path]) -> Dict[str, Any]:
        """Copy a file or directory safely."""
        src = self.canonicalize(source)
        dst = self.canonicalize(destination)

        if not src.exists():
            return {"success": False, "error": f"Source path '{source}' not found."}

        is_prot, reason = self.is_protected_path(dst)
        if is_prot:
            return {"success": False, "error": f"Destination error: {reason}"}

        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return {
                "success": True,
                "source": str(src),
                "destination": str(dst),
                "message": f"Copied '{src.name}' to '{dst}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_path(self, source: Union[str, Path], destination: Union[str, Path]) -> Dict[str, Any]:
        """Move or rename a file or directory."""
        src = self.canonicalize(source)
        dst = self.canonicalize(destination)

        if not src.exists():
            return {"success": False, "error": f"Source path '{source}' not found."}

        is_prot_src, reason_src = self.is_protected_path(src)
        if is_prot_src:
            return {"success": False, "error": f"Cannot move protected source: {reason_src}"}

        is_prot_dst, reason_dst = self.is_protected_path(dst)
        if is_prot_dst:
            return {"success": False, "error": f"Cannot move into protected destination: {reason_dst}"}

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {
                "success": True,
                "source": str(src),
                "destination": str(dst),
                "message": f"Moved '{src.name}' to '{dst}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compress_folder(self, folder_path: Union[str, Path], zip_path: Union[str, Path]) -> Dict[str, Any]:
        """Compress directory into a ZIP archive."""
        src = self.canonicalize(folder_path)
        dst = self.canonicalize(zip_path)

        if not src.exists() or not src.is_dir():
            return {"success": False, "error": f"Folder '{folder_path}' not found or is not a directory."}

        is_prot, reason = self.is_protected_path(dst)
        if is_prot:
            return {"success": False, "error": f"Cannot write ZIP to protected destination: {reason}"}

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            target_base = str(dst)[:-4] if str(dst).lower().endswith(".zip") else str(dst)
            shutil.make_archive(target_base, "zip", str(src))
            out_file = target_base + ".zip"
            return {
                "success": True,
                "folder": str(src),
                "zip_path": out_file,
                "size_bytes": os.path.getsize(out_file),
                "message": f"Compressed '{src.name}' into '{out_file}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_zip(self, zip_path: Union[str, Path], extract_to: Union[str, Path]) -> Dict[str, Any]:
        """Safely extract ZIP archive with Zip-Slip path traversal protection."""
        z = self.canonicalize(zip_path)
        out = self.canonicalize(extract_to)

        if not z.exists() or not z.is_file():
            return {"success": False, "error": f"ZIP file '{zip_path}' not found."}

        is_prot, reason = self.is_protected_path(out)
        if is_prot:
            return {"success": False, "error": f"Cannot extract into protected directory: {reason}"}

        try:
            out.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(z, "r") as archive:
                # Zip-Slip Guard: verify every file target is inside out directory
                for member in archive.infolist():
                    target = (out / member.filename).resolve()
                    if not target.is_relative_to(out):
                        return {
                            "success": False,
                            "error": f"Security Error: Archive entry '{member.filename}' escapes destination directory (Zip-Slip attempt).",
                        }
                # Safe to extract
                archive.extractall(out)
            return {
                "success": True,
                "zip_path": str(z),
                "extract_to": str(out),
                "message": f"Extracted '{z.name}' to '{out}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_path(self, path: Union[str, Path]) -> Dict[str, Any]:
        """
        Delete file or directory.
        HIGH-IMPACT operation requiring security policy check prior to execution.
        """
        target = self.canonicalize(path)
        if not target.exists():
            return {"success": False, "error": f"Path '{path}' not found."}

        is_prot, reason = self.is_protected_path(target)
        if is_prot:
            return {"success": False, "error": f"Security Error: Deleting protected system path '{target}' is forbidden. {reason}"}

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return {
                "success": True,
                "path": str(target),
                "message": f"Deleted '{target.name}' permanently.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
native_fs = NativeFileSystem()
