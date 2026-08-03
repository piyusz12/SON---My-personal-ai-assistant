# agents/desktop_agent.py — Desktop & Hardware Agent for SON V3
from core.config import Config


class DesktopAgent:
    """
    Coordinates desktop window state, system controls, and app executions.
    """

    def __init__(self, plugin_registry=None, state=None):
        self.plugins = plugin_registry
        self.state = state

    def open_workspace(self, workspace_name: str) -> str:
        """Launch a pre-configured workspace setup (e.g. 'AI workspace', 'coding')."""
        name = workspace_name.lower()
        if "ai" in name or "coding" in name or "dev" in name:
            res = []
            if self.plugins.has_tool("open_application"):
                res.append(self.plugins.call("open_application", {"name": "VS Code"}))
                res.append(self.plugins.call("open_application", {"name": "Windows Terminal"}))
            if self.plugins.has_tool("docker_list_containers"):
                res.append(self.plugins.call("docker_list_containers", {}))
            return "\n".join(res)
        
        return f"Unknown workspace profile: '{workspace_name}'."
