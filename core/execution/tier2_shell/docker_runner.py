# core/execution/tier2_shell/docker_runner.py — Tier 2 Typed Docker Integration
"""
Typed Docker container and image operations via ControlledPowerShellRunner.
Validates container identifiers, prevents flag injection, and gracefully handles
Docker daemon unavailability without crashing.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from core.execution.tier2_shell.powershell_runner import controlled_shell

logger = logging.getLogger(__name__)


def validate_container_name(container: str) -> Tuple[bool, str]:
    """Validate container identifier to prevent flag injection or shell corruption."""
    c = (container or "").strip()
    if not c:
        return False, "Container name or ID cannot be empty."
    if c.startswith("-"):
        return False, f"Invalid container identifier '{container}': leading flags are not allowed."
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", c) or len(c) > 128:
        return False, f"Invalid container identifier '{container}': must be alphanumeric with ., _, or -."
    return True, ""


class DockerRunner:
    """Tier 2 Docker Management Engine."""

    def __init__(self, runner=None):
        self.runner = runner or controlled_shell

    def check_status(self) -> Dict[str, Any]:
        """Check if Docker CLI exists and daemon is responsive."""
        res = self.runner.run_process("docker", ["version", "--format", "{{.Server.Version}}"], timeout_seconds=5.0)
        is_running = res.success and bool(res.stdout.strip())
        return {
            "success": True,
            "installed": res.returncode != -1,
            "daemon_running": is_running,
            "server_version": res.stdout.strip() if is_running else None,
            "message": "Docker daemon is running." if is_running else "Docker is installed but the daemon is not running.",
        }

    def list_containers(self, all_containers: bool = True) -> Dict[str, Any]:
        """List Docker containers with their ID, name, status, and image (READ)."""
        args = ["ps", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"]
        if all_containers:
            args.insert(1, "-a")

        res = self.runner.run_process("docker", args, timeout_seconds=15.0)
        if not res.success:
            return {
                "success": False,
                "error": res.stderr or "Failed to list containers (is Docker running?).",
                "output": "",
            }
        return {
            "success": True,
            "output": res.stdout if res.stdout else "No containers found.",
            "count": len(res.stdout.strip().splitlines()) - 1 if res.stdout else 0,
        }

    def list_images(self) -> Dict[str, Any]:
        """List local Docker images (READ)."""
        res = self.runner.run_process(
            "docker",
            ["images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}"],
            timeout_seconds=15.0,
        )
        return {
            "success": res.success,
            "output": res.stdout if res.success else res.stderr,
            "error": res.error_message,
        }

    def inspect_container(self, container: str) -> Dict[str, Any]:
        """Inspect container configuration and status (READ)."""
        ok, err = validate_container_name(container)
        if not ok:
            return {"success": False, "error": f"Security Error: {err}"}

        res = self.runner.run_process("docker", ["inspect", container.strip()], timeout_seconds=10.0)
        return {
            "success": res.success,
            "output": res.stdout if res.success else res.stderr,
            "error": res.error_message,
        }

    def start_container(self, container: str) -> Dict[str, Any]:
        """Start container by name or ID (LOCAL_REVERSIBLE)."""
        ok, err = validate_container_name(container)
        if not ok:
            return {"success": False, "error": f"Security Error: {err}"}

        res = self.runner.run_process("docker", ["start", container.strip()], timeout_seconds=30.0)
        return {
            "success": res.success,
            "message": f"Started container '{container}'." if res.success else f"Failed to start container: {res.stderr}",
            "container": container,
            "error": res.error_message,
        }

    def stop_container(self, container: str, timeout_seconds: int = 10) -> Dict[str, Any]:
        """Stop running container safely (LOCAL_REVERSIBLE)."""
        ok, err = validate_container_name(container)
        if not ok:
            return {"success": False, "error": f"Security Error: {err}"}

        res = self.runner.run_process(
            "docker",
            ["stop", "-t", str(timeout_seconds), container.strip()],
            timeout_seconds=float(timeout_seconds + 5),
        )
        return {
            "success": res.success,
            "message": f"Stopped container '{container}'." if res.success else f"Failed to stop container: {res.stderr}",
            "container": container,
            "error": res.error_message,
        }

    def restart_container(self, container: str) -> Dict[str, Any]:
        """Restart container (LOCAL_REVERSIBLE)."""
        ok, err = validate_container_name(container)
        if not ok:
            return {"success": False, "error": f"Security Error: {err}"}

        res = self.runner.run_process("docker", ["restart", container.strip()], timeout_seconds=30.0)
        return {
            "success": res.success,
            "message": f"Restarted container '{container}'." if res.success else f"Failed to restart container: {res.stderr}",
            "container": container,
            "error": res.error_message,
        }

    def logs(self, container: str, lines: int = 50) -> Dict[str, Any]:
        """Fetch recent container logs (READ)."""
        ok, err = validate_container_name(container)
        if not ok:
            return {"success": False, "error": f"Security Error: {err}"}

        clamped_lines = max(1, min(1000, int(lines)))
        res = self.runner.run_process("docker", ["logs", "--tail", str(clamped_lines), container.strip()], timeout_seconds=15.0)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "container": container,
            "error": res.error_message,
        }

    def build_image(self, dockerfile_path: str, tag: Optional[str] = None) -> Dict[str, Any]:
        """Build image from Dockerfile (HIGH_IMPACT / approval)."""
        args = ["build", "-f", dockerfile_path]
        if tag:
            args.extend(["-t", tag])
        args.append(".")

        res = self.runner.run_process("docker", args, timeout_seconds=300.0)
        return {
            "success": res.success,
            "output": res.stdout or res.stderr,
            "error": res.error_message,
        }


# Singleton instance
docker_runner = DockerRunner()
