# plugins/docker.py — Docker Management Plugin for SON V3
import subprocess
from core.config import SecurityLevel
from plugins.base import BasePlugin


class DockerPlugin(BasePlugin):
    """
    Manages Docker Desktop, containers, images, logs, and stats.
    """

    def __init__(self):
        super().__init__(name="docker", description="Docker Desktop container manager", category="docker")

    def initialize(self):
        self.register_tool(
            "docker_list_containers", self.list_containers,
            description="List Docker containers with status, ports, and image name",
            params={"all_containers": {"type": "boolean", "default": True}},
            security_level=SecurityLevel.SAFE
        )
        self.register_tool(
            "docker_start_container", self.start_container,
            description="Start a Docker container",
            params={"container": {"type": "string", "description": "Container name or ID"}},
            required=["container"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "docker_stop_container", self.stop_container,
            description="Stop a running Docker container",
            params={"container": {"type": "string", "description": "Container name or ID"}},
            required=["container"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "docker_restart_container", self.restart_container,
            description="Restart a Docker container",
            params={"container": {"type": "string", "description": "Container name or ID"}},
            required=["container"], security_level=SecurityLevel.MEDIUM
        )
        self.register_tool(
            "docker_logs", self.get_logs,
            description="Get recent container log lines",
            params={
                "container": {"type": "string", "description": "Container name or ID"},
                "lines": {"type": "integer", "default": 50}
            },
            required=["container"], security_level=SecurityLevel.SAFE
        )

    # ── Implementations ───────────────────────────────────────

    @staticmethod
    def _validate_container_name(container: str) -> tuple[bool, str]:
        c = (container or "").strip()
        if not c:
            return False, "Container name or ID cannot be empty."
        if c.startswith("-"):
            return False, f"Invalid container name '{container}': leading flags are not allowed."
        import re
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", c) or len(c) > 128:
            return False, f"Invalid container identifier '{container}': must be alphanumeric with ., _, or -."
        return True, ""

    def _cmd(self, args: list[str]) -> tuple[bool, str]:
        try:
            res = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=15)
            return (res.returncode == 0, res.stdout.strip() or res.stderr.strip())
        except Exception as e:
            return (False, f"Docker command failed: {e}")

    def list_containers(self, all_containers: bool = True) -> str:
        args = ["ps", "-a" if all_containers else "", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"]
        args = [a for a in args if a]
        ok, out = self._cmd(args)
        return out if ok and out else "No Docker containers found."

    def start_container(self, container: str) -> str:
        valid, err = self._validate_container_name(container)
        if not valid:
            return f"Security Error: {err}"
        ok, out = self._cmd(["start", container.strip()])
        return f"Started container '{container}'." if ok else f"Failed to start: {out}"

    def stop_container(self, container: str) -> str:
        valid, err = self._validate_container_name(container)
        if not valid:
            return f"Security Error: {err}"
        ok, out = self._cmd(["stop", container.strip()])
        return f"Stopped container '{container}'." if ok else f"Failed to stop: {out}"

    def restart_container(self, container: str) -> str:
        valid, err = self._validate_container_name(container)
        if not valid:
            return f"Security Error: {err}"
        ok, out = self._cmd(["restart", container.strip()])
        return f"Restarted container '{container}'." if ok else f"Failed to restart: {out}"

    def get_logs(self, container: str, lines: int = 50) -> str:
        valid, err = self._validate_container_name(container)
        if not valid:
            return f"Security Error: {err}"
        try:
            line_count = int(lines)
            if line_count < 1 or line_count > 5000:
                line_count = 50
        except (ValueError, TypeError):
            line_count = 50

        ok, out = self._cmd(["logs", "--tail", str(line_count), container.strip()])
        return out if ok else f"Failed to fetch logs: {out}"
