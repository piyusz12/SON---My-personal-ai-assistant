# agents/desktop_agent.py — Desktop & Hardware Agent for SON V3
from core.orchestrator import orchestrator as global_orch
from core.security.context import create_trusted_context


class DesktopAgent:
    """
    Coordinates desktop window state, system controls, and app executions.
    Routes all actions through the central SonOrchestrator.
    """

    def __init__(self, plugin_registry=None, state=None, user_id: str = "primary_user"):
        self.plugins = plugin_registry
        self.state = state
        self.user_id = user_id

    def open_workspace(self, workspace_name: str, session_id: str | None = None) -> str:
        """Launch a pre-configured workspace setup (e.g. 'AI workspace', 'coding')."""
        name = workspace_name.lower()
        if "ai" in name or "coding" in name or "dev" in name:
            res = []
            ctx = create_trusted_context(
                user_id=self.user_id,
                interface_type="desktop_agent",
                session_id=session_id,
            )
            # Open VS Code safely through orchestrator
            res1 = global_orch.execute_action("open_application", {"name": "VS Code"}, context=ctx)
            res.append(res1.output)

            # Open Windows Terminal safely through orchestrator
            res2 = global_orch.execute_action("open_application", {"name": "Windows Terminal"}, context=ctx)
            res.append(res2.output)

            # List docker containers safely through orchestrator
            res3 = global_orch.execute_action("docker_list_containers", {}, context=ctx)
            res.append(res3.output)

            return "\n".join(res)

        return f"Unknown workspace profile: '{workspace_name}'."
