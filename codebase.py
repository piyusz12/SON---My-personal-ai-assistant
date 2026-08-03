# codebase.py — Code Scanner, Embedder & Git-Aware Progress Tracker
import os
import hashlib
import fnmatch
from pathlib import Path
from datetime import datetime

import config


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

    # ── File Discovery ────────────────────────────────────────

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path matches any ignore pattern."""
        path_str = str(path)
        for pattern in self._ignore_patterns:
            # Check each part of the path
            for part in path.parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            # Also check full path
            if fnmatch.fnmatch(path_str, f"*{pattern}*"):
                return True
        return False

    def _discover_files(self, project_path: str) -> list[Path]:
        """Recursively discover code files in a project directory."""
        root = Path(project_path)
        if not root.exists():
            return []

        files = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if self._should_ignore(file_path):
                continue
            if file_path.suffix not in self._extensions:
                continue
            if file_path.stat().st_size > self._max_file_size:
                continue
            files.append(file_path)

        return sorted(files)

    # ── Chunking ──────────────────────────────────────────────

    def _chunk_file(self, file_path: Path) -> list[dict]:
        """
        Split a file into overlapping chunks for embedding.
        Each chunk includes metadata about its origin.
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        if not content.strip():
            return []

        chunks = []
        lines = content.split("\n")
        current_chunk = []
        current_len = 0
        start_line = 1

        for i, line in enumerate(lines, 1):
            current_chunk.append(line)
            current_len += len(line) + 1  # +1 for newline

            if current_len >= self._chunk_size:
                chunk_text = "\n".join(current_chunk)
                chunk_id = self._make_chunk_id(file_path, start_line)

                chunks.append({
                    "id": chunk_id,
                    "content": chunk_text,
                    "file": str(file_path),
                    "start_line": start_line,
                    "end_line": i,
                })

                # Overlap: keep last N characters worth of lines
                overlap_lines = []
                overlap_len = 0
                for ln in reversed(current_chunk):
                    overlap_len += len(ln) + 1
                    overlap_lines.insert(0, ln)
                    if overlap_len >= self._chunk_overlap:
                        break

                current_chunk = overlap_lines
                current_len = overlap_len
                start_line = i - len(overlap_lines) + 1

        # Remaining lines
        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunk_id = self._make_chunk_id(file_path, start_line)
            chunks.append({
                "id": chunk_id,
                "content": chunk_text,
                "file": str(file_path),
                "start_line": start_line,
                "end_line": len(lines),
            })

        return chunks

    def _make_chunk_id(self, file_path: Path, start_line: int) -> str:
        """Create a deterministic chunk ID."""
        raw = f"{file_path}:{start_line}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Scanning & Embedding ──────────────────────────────────

    def scan(self, project_path: str | None = None, on_progress=None) -> dict:
        """
        Scan a project directory, chunk all code files, and embed them.

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

            for i, file_path in enumerate(files):
                if on_progress:
                    on_progress(i + 1, len(files), file_path.name)

                chunks = self._chunk_file(file_path)

                for chunk in chunks:
                    rel_path = str(file_path.relative_to(proj_path))
                    self._memory.store_code_chunk(
                        chunk_id=chunk["id"],
                        content=chunk["content"],
                        metadata={
                            "file": rel_path,
                            "project": project_name,
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "extension": file_path.suffix,
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
        except Exception:
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
        except Exception:
            pass

        return commits

    def get_diff_summary(self, project_path: str) -> str:
        """Get a summary of uncommitted changes."""
        repo = self._get_repo(project_path)
        if not repo:
            return "Not a git repository."

        try:
            # Staged changes
            staged = repo.index.diff("HEAD")
            # Unstaged changes
            unstaged = repo.index.diff(None)
            # Untracked files
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
        """
        Generate a progress report based on recent git activity.
        """
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

            # Build report
            report_lines = [
                f"Progress Report — Last {days} days",
                f"Total commits: {len(commits)}",
                "",
            ]

            # Unique files changed
            all_files = set()
            for c in commits:
                all_files.update(c["files"])

            report_lines.append(f"Files touched: {len(all_files)}")
            report_lines.append("")

            # List commits
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
