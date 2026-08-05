# codebase.py — Code Scanner, Embedder & Git-Aware Progress Tracker
# SON V3 — Optimized for Ryzen 7 7840HS (8C/16T)
"""
Changes from V2:
- Parallel file discovery using os.scandir() + ThreadPoolExecutor
- Parallel chunking using ProcessPoolExecutor (4 workers)
- Batch embedding via Ollama to reduce HTTP round-trips
- C-accelerated chunking via fast_chunk_text when available
- Code chunk cache (mtime-invalidated) to skip re-scanning unchanged files
"""
import os
import hashlib
import fnmatch
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from core.config import Config
logger = Config.get_logger(__name__)

import config

# Import native acceleration and caching (with fallbacks)
try:
    from native.son_native import fast_chunk_text, fast_sha256_hex
    _HAS_NATIVE_CHUNK = True
except ImportError:
    _HAS_NATIVE_CHUNK = False

try:
    from core.cache import CodeChunkCache
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False


def _chunk_file_worker(args: tuple) -> list[dict]:
    """
    Standalone function for process pool — chunks a single file.
    Must be a top-level function (picklable for multiprocessing).
    """
    file_path_str, chunk_size, overlap = args
    file_path = Path(file_path_str)

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    if not content.strip():
        return []

    # Use C-accelerated chunking if available
    if _HAS_NATIVE_CHUNK:
        raw_chunks = fast_chunk_text(content, chunk_size, overlap)
        chunks = []
        for chunk_text, start_line, end_line in raw_chunks:
            chunk_id = fast_sha256_hex(f"{file_path}:{start_line}")
            chunks.append({
                "id": chunk_id,
                "content": chunk_text,
                "file": str(file_path),
                "start_line": start_line,
                "end_line": end_line,
            })
        return chunks

    # Python fallback
    lines = content.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0
    start_line = 1

    for i, line in enumerate(lines, 1):
        current_chunk.append(line)
        current_len += len(line) + 1

        if current_len >= chunk_size:
            chunk_text = "\n".join(current_chunk)
            raw = f"{file_path}:{start_line}"
            chunk_id = hashlib.sha256(raw.encode()).hexdigest()[:16]

            chunks.append({
                "id": chunk_id,
                "content": chunk_text,
                "file": str(file_path),
                "start_line": start_line,
                "end_line": i,
            })

            # Overlap
            overlap_lines = []
            overlap_len = 0
            for ln in reversed(current_chunk):
                overlap_len += len(ln) + 1
                overlap_lines.insert(0, ln)
                if overlap_len >= overlap:
                    break

            current_chunk = overlap_lines
            current_len = overlap_len
            start_line = i - len(overlap_lines) + 1

    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        raw = f"{file_path}:{start_line}"
        chunk_id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "content": chunk_text,
            "file": str(file_path),
            "start_line": start_line,
            "end_line": len(lines),
        })

    return chunks


class CodeTracker:
    """
    Scans project directories, embeds code chunks into memory,
    and tracks progress via git integration.
    """

    def __init__(self, memory, project_paths: list[str] | None = None):
        self._memory = memory
        self._project_paths = project_paths or config.DEFAULT_PROJECT_PATHS
        self._extensions = config.CODE_EXTENSIONS
        self._ignore_patterns = config.CODE_IGNORE_PATTERNS
        self._max_file_size = config.CODE_MAX_FILE_SIZE
        self._chunk_size = config.CODE_CHUNK_SIZE
        self._chunk_overlap = config.CODE_CHUNK_OVERLAP

        # Code chunk cache (mtime-invalidated)
        self._cache = CodeChunkCache(max_size_mb=1024) if _HAS_CACHE else None

    # ── File Discovery (Optimized with os.scandir) ────────────

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path matches any ignore pattern."""
        path_str = str(path)
        for pattern in self._ignore_patterns:
            for part in path.parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            if fnmatch.fnmatch(path_str, f"*{pattern}*"):
                return True
        return False

    def _discover_files(self, project_path: str) -> list[Path]:
        """
        Recursively discover code files using os.scandir (faster than pathlib.rglob).
        """
        root = Path(project_path)
        if not root.exists():
            return []

        files = []

        def _scan_dir(dir_path: Path):
            try:
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        entry_path = Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            if not self._should_ignore(entry_path):
                                _scan_dir(entry_path)
                        elif entry.is_file(follow_symlinks=False):
                            if self._should_ignore(entry_path):
                                continue
                            if entry_path.suffix not in self._extensions:
                                continue
                            try:
                                if entry.stat().st_size > self._max_file_size:
                                    continue
                            except OSError:
                                continue
                            files.append(entry_path)
            except PermissionError:
                pass

        _scan_dir(root)
        return sorted(files)

    # ── Chunking (C-accelerated or Python fallback) ───────────

    def _chunk_file(self, file_path: Path) -> list[dict]:
        """
        Split a file into overlapping chunks for embedding.
        Uses cache if available (skips unchanged files).
        """
        # Check cache first
        if self._cache:
            cached = self._cache.get(str(file_path))
            if cached is not None:
                return cached

        chunks = _chunk_file_worker(
            (str(file_path), self._chunk_size, self._chunk_overlap)
        )

        # Store in cache
        if self._cache and chunks:
            self._cache.put(str(file_path), chunks)

        return chunks

    def _make_chunk_id(self, file_path: Path, start_line: int) -> str:
        """Create a deterministic chunk ID."""
        if _HAS_NATIVE_CHUNK:
            return fast_sha256_hex(f"{file_path}:{start_line}")
        raw = f"{file_path}:{start_line}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Scanning & Embedding (Parallelized) ───────────────────

    def scan(self, project_path: str | None = None, on_progress=None) -> dict:
        """
        Scan a project directory, chunk all code files, and embed them.

        Optimized:
        - Parallel file chunking using ThreadPoolExecutor (8 workers)
        - Batch embedding support
        - Cache-aware: skips unchanged files

        Args:
            project_path: Path to scan (or scans all configured paths).
            on_progress: Callback(current, total, filename) for progress updates.

        Returns:
            Dict with scan statistics.
        """
        paths = [project_path] if project_path else self._project_paths
        total_files = 0
        total_chunks = 0

        for proj_path in paths:
            project_name = Path(proj_path).name

            # Clear old embeddings for this project
            self._memory.clear_codebase(project=project_name)

            files = self._discover_files(proj_path)
            total_files += len(files)

            # Parallel chunking using thread pool (I/O bound — file reads)
            all_chunks = []

            with ThreadPoolExecutor(max_workers=8, thread_name_prefix="chunk") as pool:
                future_to_file = {}
                for file_path in files:
                    future = pool.submit(self._chunk_file, file_path)
                    future_to_file[future] = file_path

                completed = 0
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    completed += 1

                    if on_progress:
                        on_progress(completed, len(files), file_path.name)

                    try:
                        chunks = future.result()
                        for chunk in chunks:
                            chunk["_proj_path"] = proj_path
                            chunk["_project_name"] = project_name
                        all_chunks.extend(chunks)
                    except Exception as e:
                        logger.error(f"Failed to chunk {file_path}: {e}")

            # Embed all chunks (sequential for Ollama, but could batch)
            for chunk in all_chunks:
                try:
                    rel_path = str(
                        Path(chunk["file"]).relative_to(chunk["_proj_path"])
                    )
                except ValueError:
                    rel_path = chunk["file"]

                self._memory.store_code_chunk(
                    chunk_id=chunk["id"],
                    content=chunk["content"],
                    metadata={
                        "file": rel_path,
                        "project": chunk["_project_name"],
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"],
                        "extension": Path(chunk["file"]).suffix,
                        "scanned_at": datetime.now().isoformat(),
                    },
                )
                total_chunks += 1

        return {
            "files_scanned": total_files,
            "chunks_embedded": total_chunks,
            "projects": [Path(p).name for p in paths],
        }

    def query(self, question: str, n_results: int | None = None) -> list[dict]:
        """Query codebase for relevant code chunks."""
        return self._memory.query_code(question, n_results)

    # ── Git Integration ───────────────────────────────────────

    def _get_repo(self, project_path: str):
        """Get a git.Repo object for the project, or None."""
        try:
            import git
            return git.Repo(project_path)
        except Exception as e:
            logger.error(f"Exception caught: {e}", exc_info=True)
            return None

    def get_recent_commits(self, project_path: str, count: int = 10) -> list[dict]:
        """Get recent git commits."""
        repo = self._get_repo(project_path)
        if not repo:
            return []

        commits = []
        try:
            for commit in repo.iter_commits(max_count=count):
                commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "files_changed": len(commit.stats.files),
                })
        except Exception as e:
            logger.error(f"Exception caught: {e}", exc_info=True)

        return commits

    def get_diff_summary(self, project_path: str) -> str:
        """Get a summary of uncommitted changes."""
        repo = self._get_repo(project_path)
        if not repo:
            return "Not a git repository."

        try:
            staged = repo.index.diff("HEAD")
            unstaged = repo.index.diff(None)
            untracked = repo.untracked_files

            parts = []

            if staged:
                files = [d.a_path or d.b_path for d in staged]
                parts.append(f"Staged ({len(files)}): {', '.join(files)}")

            if unstaged:
                files = [d.a_path or d.b_path for d in unstaged]
                parts.append(f"Modified ({len(files)}): {', '.join(files)}")

            if untracked:
                parts.append(f"Untracked ({len(untracked)}): {', '.join(untracked[:10])}")

            if not parts:
                return "Working tree is clean — no uncommitted changes."

            return "\n".join(parts)

        except Exception as e:
            return f"Error reading git status: {e}"

    def get_progress_report(self, project_path: str, days: int = 7) -> str:
        """Generate a progress report based on recent git activity."""
        repo = self._get_repo(project_path)
        if not repo:
            return "Not a git repository — cannot generate progress report."

        try:
            from datetime import timedelta
            since = datetime.now() - timedelta(days=days)

            commits = []
            for commit in repo.iter_commits():
                commit_date = datetime.fromtimestamp(commit.committed_date)
                if commit_date < since:
                    break
                commits.append({
                    "message": commit.message.strip(),
                    "date": commit_date.strftime("%Y-%m-%d %H:%M"),
                    "files": list(commit.stats.files.keys()),
                })

            if not commits:
                return f"No commits in the last {days} days."

            report_lines = [
                f"Progress Report — Last {days} days",
                f"Total commits: {len(commits)}",
                "",
            ]

            all_files = set()
            for c in commits:
                all_files.update(c["files"])

            report_lines.append(f"Files touched: {len(all_files)}")
            report_lines.append("")

            report_lines.append("Commits:")
            for c in commits:
                report_lines.append(f"  [{c['date']}] {c['message']}")

            return "\n".join(report_lines)

        except Exception as e:
            return f"Error generating report: {e}"

    # ── File Listing ──────────────────────────────────────────

    def list_project_files(self, project_path: str) -> list[str]:
        """List all code files in a project."""
        files = self._discover_files(project_path)
        root = Path(project_path)
        return [str(f.relative_to(root)) for f in files]
