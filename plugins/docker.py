# plugins/docker.py — Docker Management Plugin for SON V3
"""
Docker Management Plugin for SON V3.
Delegates all Docker container lifecycle management to tools.docker_control.
"""
from core.config import SecurityLevel
from plugins.base import BasePlugin
from tools import docker_control


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

    # ── Tool Implementations (Delegating to tools.docker_control) ────────

    _validate_container_name = staticmethod(docker_control._validate_container_name)

    def list_containers(self, all_containers: bool = True) -> str:
        return docker_control.docker_list_containers(all_containers=all_containers)

    def start_container(self, container: str) -> str:
        return docker_control.docker_start(container=container)

    def stop_container(self, container: str) -> str:
        return docker_control.docker_stop(container=container)

    def restart_container(self, container: str) -> str:
        return docker_control.docker_restart(container=container)

    def get_logs(self, container: str, lines: int = 50) -> str:
        return docker_control.docker_logs(container=container, lines=lines)
