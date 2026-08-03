# plugins/files.py — File Manager Plugin for SON V3
import os
import shutil
import zipfile
from pathlib import Path
from core.config import SecurityLevel
from plugins.base import BasePlugin


class FilesPlugin(BasePlugin):
    """
    Manages local files and directories: search, copy, move, rename, delete, zip, extract.
    """

    def __init__(self):
        super().__init__(name="files", description="Local file and directory manager", category="files")

    def initialize(self):
        self.register_tool(
            "search_files", self.search_files,
            description="Search for files by name pattern",
            params={
                "query": {"type": "string", "description": "Filename pattern to match"},
                "directory": {"type": "string", "description": "Root directory to search", "default": str(Path.home())}
            },
            required=["query"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "open_folder", self.open_folder,
            description="Open a directory in Windows File Explorer",
            params={"path": {"type": "string", "description": "Folder path"}},
            required=["path"], security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "copy_path", self.copy_path,
            description="Copy a file or directory to a new location",
            params={
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"}
            },
            required=["source", "destination"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "move_path", self.move_path,
            description="Move or rename a file or directory",
            params={
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"}
            },
            required=["source", "destination"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "delete_path", self.delete_path,
            description="Delete a file or directory permanently",
            params={"path": {"type": "string", "description": "Target path to delete"}},
            required=["path"], security_level=SecurityLevel.SENSITIVE
        )
        self.register_tool(
            "compress_folder", self.compress_folder,
            description="Compress a directory into a ZIP archive",
            params={
                "folder_path": {"type": "string", "description": "Folder path to compress"},
                "zip_path": {"type": "string", "description": "Output ZIP file path"}
            },
            required=["folder_path", "zip_path"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "extract_zip", self.extract_zip,
            description="Extract a ZIP archive to a target directory",
            params={
                "zip_path": {"type": "string", "description": "ZIP file path"},
                "extract_to": {"type": "string", "description": "Destination folder"}
            },
            required=["zip_path", "extract_to"], security_level=SecurityLevel.MEDIUM
        )

    # ── Implementations ───────────────────────────────────────

    def search_files(self, query: str, directory: str = "") -> str:
        root = Path(directory) if directory else Path.home()
        if not root.exists():
            return f"Directory '{directory}' does not exist."

        results = []
        try:
            for p in root.rglob(f"*{query}*"):
                if len(results) >= 20:
                    break
                try:
                    size_mb = p.stat().st_size / (1024 * 1024)
                    results.append(f"• {p} ({size_mb:.2f} MB)")
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            return f"Error searching files: {e}"

        return "\n".join(results) if results else f"No files matching '{query}' found."

    def open_folder(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Path does not exist: {path}"
        os.startfile(str(p))
        return f"Opened folder '{p.name}' in Explorer."

    def copy_path(self, source: str, destination: str) -> str:
        src, dst = Path(source), Path(destination)
        if not src.exists():
            return f"Source path '{source}' not found."
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return f"Copied '{src.name}' to '{dst}'."
        except Exception as e:
            return f"Failed to copy: {e}"

    def move_path(self, source: str, destination: str) -> str:
        src, dst = Path(source), Path(destination)
        if not src.exists():
            return f"Source path '{source}' not found."
        try:
            shutil.move(str(src), str(dst))
            return f"Moved '{src.name}' to '{dst}'."
        except Exception as e:
            return f"Failed to move: {e}"

    def delete_path(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f"Path '{path}' not found."
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return f"Deleted '{p.name}' permanently."
        except Exception as e:
            return f"Failed to delete: {e}"

    def compress_folder(self, folder_path: str, zip_path: str) -> str:
        src = Path(folder_path)
        dst = Path(zip_path)
        if not src.exists() or not src.is_dir():
            return f"Folder '{folder_path}' not found or is not a directory."
        try:
            shutil.make_archive(str(dst.with_suffix("")), 'zip', str(src))
            return f"Compressed '{src.name}' into '{dst.with_suffix('.zip')}'."
        except Exception as e:
            return f"Failed to compress folder: {e}"

    def extract_zip(self, zip_path: str, extract_to: str) -> str:
        z = Path(zip_path)
        out = Path(extract_to)
        if not z.exists() or not z.name.endswith(".zip"):
            return f"ZIP file '{zip_path}' not found."
        try:
            with zipfile.ZipFile(z, 'r') as archive:
                archive.extractall(out)
            return f"Extracted '{z.name}' to '{out}'."
        except Exception as e:
            return f"Failed to extract ZIP: {e}"
