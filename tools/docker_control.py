# tools/docker_control.py — Docker Management Tools for SON
"""
Docker container management tools.
Uses the Docker CLI (docker must be in PATH).
"""
import subprocess
import json
import re


def _validate_container_name(container: str) -> tuple[bool, str]:
    """Validate container name or ID to prevent command injection and flag injection."""
    c = (container or "").strip()
    if not c:
        return False, "Container name or ID cannot be empty."
    if c.startswith("-"):
        return False, f"Invalid container name '{container}': leading flags are not allowed."
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", c) or len(c) > 128:
        return False, f"Invalid container identifier '{container}': must be alphanumeric with ., _, or -."
    return True, ""


validate_container_name = _validate_container_name


def _docker_cmd(args: list[str], timeout: int = 15) -> tuple[bool, str]:
    """Run a docker command and return (success, output)."""
    try:
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except FileNotFoundError:
        return False, "Docker CLI not found. Is Docker installed and in PATH?"
    except subprocess.TimeoutExpired:
        return False, f"Docker command timed out after {timeout}s."
    except Exception as e:
        return False, f"Docker error: {e}"


def docker_list_containers(all_containers: bool = True) -> str:
    """List Docker containers with their status."""
    args = ["ps", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"]
    if all_containers:
        args.insert(1, "-a")

    ok, output = _docker_cmd(args)
    if not ok:
        return f"Failed to list containers: {output}"
    return output if output else "No containers found."


def docker_start(container: str) -> str:
    """Start a Docker container by name or ID."""
    valid, err = _validate_container_name(container)
    if not valid:
        return f"Security Error: {err}"
    ok, output = _docker_cmd(["start", container.strip()])
    if ok:
        return f"Started container '{container}'."
    return f"Failed to start '{container}': {output}"


def docker_stop(container: str) -> str:
    """Stop a Docker container by name or ID."""
    valid, err = _validate_container_name(container)
    if not valid:
        return f"Security Error: {err}"
    ok, output = _docker_cmd(["stop", container.strip()])
    if ok:
        return f"Stopped container '{container}'."
    return f"Failed to stop '{container}': {output}"


def docker_restart(container: str) -> str:
    """Restart a Docker container by name or ID."""
    valid, err = _validate_container_name(container)
    if not valid:
        return f"Security Error: {err}"
    ok, output = _docker_cmd(["restart", container.strip()])
    if ok:
        return f"Restarted container '{container}'."
    return f"Failed to restart '{container}': {output}"


def docker_logs(container: str, lines: int = 50) -> str:
    """Get recent logs from a Docker container."""
    valid, err = _validate_container_name(container)
    if not valid:
        return f"Security Error: {err}"
    ok, output = _docker_cmd(["logs", "--tail", str(int(lines)), container.strip()])
    if not ok:
        return f"Failed to get logs for '{container}': {output}"
    return output if output else "No logs available."


docker_start_container = docker_start
docker_stop_container = docker_stop
docker_restart_container = docker_restart


def docker_stats() -> str:
    """Get resource usage stats for running containers."""
    ok, output = _docker_cmd(
        ["stats", "--no-stream", "--format",
         "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"],
        timeout=10,
    )
    if not ok:
        return f"Failed to get stats: {output}"
    return output if output else "No running containers."


# ═══════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════

def register_all(registry):
    """Register all Docker tools with a ToolRegistry."""
    from core.config import SecurityLevel

    registry.register(
        name="docker_list_containers",
        func=docker_list_containers,
        description="List all Docker containers with their status, image, and ports",
        params={
            "all_containers": {
                "type": "boolean",
                "description": "If true, show all containers including stopped ones",
                "default": True,
            }
        },
        category="docker",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="docker_start",
        func=docker_start,
        description="Start a Docker container by name or ID",
        params={"container": {"type": "string", "description": "Container name or ID"}},
        required=["container"],
        category="docker",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="docker_stop",
        func=docker_stop,
        description="Stop a running Docker container by name or ID",
        params={"container": {"type": "string", "description": "Container name or ID"}},
        required=["container"],
        category="docker",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="docker_restart",
        func=docker_restart,
        description="Restart a Docker container by name or ID",
        params={"container": {"type": "string", "description": "Container name or ID"}},
        required=["container"],
        category="docker",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="docker_logs",
        func=docker_logs,
        description="Get recent logs from a Docker container",
        params={
            "container": {"type": "string", "description": "Container name or ID"},
            "lines": {"type": "integer", "description": "Number of log lines to show", "default": 50},
        },
        required=["container"],
        category="docker",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="docker_stats",
        func=docker_stats,
        description="Get CPU, memory, and network stats for running Docker containers",
        params={},
        category="docker",
        security_level=SecurityLevel.SAFE,
    )

