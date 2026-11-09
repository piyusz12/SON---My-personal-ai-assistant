# tools/automation.py — Routine Automation Engine for SON
"""
Create, save, and execute named routines (sequences of tool calls).
Routines are persisted as JSON and can be triggered by voice or text.

Example: "morning routine" →
  1. Get weather
  2. Get news
  3. Open VS Code
  4. Start Docker
  5. Speak a briefing
"""
import json
import time
from pathlib import Path
from datetime import datetime

import config
from core.config import SecurityLevel


class AutomationEngine:
    """
    Manages saved routines — named sequences of tool calls.
    Executes steps through ActionExecutor and PolicyEngine to prevent approval bypass.
    """

    def __init__(self, tool_registry=None, executor=None, orchestrator=None, routines_file=None):
        self._registry = tool_registry
        self._executor = executor
        if orchestrator is None:
            try:
                from core.orchestrator import orchestrator as default_orch
                self._orchestrator = default_orch
            except Exception:
                self._orchestrator = None
        else:
            self._orchestrator = orchestrator
        self._routines_file = Path(routines_file or config.ROUTINES_FILE)
        self._routines: dict = {}
        self._load()

    def _load(self):
        """Load routines from disk."""
        if self._routines_file.exists():
            try:
                with open(self._routines_file, "r", encoding="utf-8", errors="replace") as f:
                    self._routines = json.load(f)
            except (json.JSONDecodeError, Exception):
                self._routines = {}
        else:
            self._routines = _default_routines()
            self._save()

    def _save(self):
        """Persist routines to disk."""
        self._routines_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._routines_file, "w", encoding="utf-8") as f:
            json.dump(self._routines, f, indent=2)

    # ── Routine CRUD ──────────────────────────────────────────

    def create_routine(self, name: str, description: str, steps: list[dict]) -> str:
        """
        Create a new routine.

        Args:
            name: Routine name (e.g. "morning").
            description: Human-readable description.
            steps: List of dicts with "tool" and "args" keys.
                   e.g. [{"tool": "get_weather", "args": {"city": "auto"}}]
        """
        self._routines[name] = {
            "description": description,
            "steps": steps,
            "created": datetime.now().isoformat(),
        }
        self._save()
        return f"Routine '{name}' created with {len(steps)} steps."

    def delete_routine(self, name: str) -> str:
        """Delete a saved routine."""
        if name in self._routines:
            del self._routines[name]
            self._save()
            return f"Routine '{name}' deleted."
        return f"Routine '{name}' not found."

    def list_routines(self) -> str:
        """List all saved routines."""
        if not self._routines:
            return "No routines saved. Create one with 'create routine'."

        lines = ["Saved Routines:\n"]
        for name, routine in self._routines.items():
            desc = routine.get("description", "No description")
            steps = len(routine.get("steps", []))
            lines.append(f"  • {name} — {desc} ({steps} steps)")

        return "\n".join(lines)

    def get_routine(self, name: str) -> dict | None:
        """Get a routine definition by name."""
        return self._routines.get(name)

    # ── Execution ─────────────────────────────────────────────

    def run_routine(self, name: str, user_id: str = "primary_user") -> str:
        """
        Execute a saved routine by name.
        Runs each step sequentially, verifying zero-trust policy decisions and executing
        through ActionExecutor or ToolRegistry to prevent approval bypasses.
        """
        routine = self._routines.get(name)
        if not routine:
            return f"Routine '{name}' not found. Available: {', '.join(self._routines.keys())}"

        steps = routine.get("steps", [])
        results = []
        results.append(f"Running routine: {name}")
        results.append(f"Description: {routine.get('description', '')}")
        results.append(f"Steps: {len(steps)}\n")

        if self._orchestrator:
            from core.security.context import SecurityContext
            ctx = SecurityContext(
                user_id=user_id,
                session_id=f"routine:{name}",
                interface_type="automation",
            )
            for i, step in enumerate(steps, 1):
                tool_name = step.get("tool", "")
                tool_args = step.get("args", {})
                approval_id = step.get("approval_id")
                results.append(f"Step {i}: {tool_name}")

                tool_func = self._registry.get_tool_func(tool_name) if hasattr(self._registry, "get_tool_func") else None
                action_res = self._orchestrator.execute_action(
                    tool_name=tool_name,
                    arguments=tool_args,
                    context=ctx,
                    approval_id=approval_id,
                    tool_func=tool_func,
                )
                if not action_res.success:
                    results.append(f"  ✖ Blocked by policy: {action_res.output}")
                else:
                    short = str(action_res.output)[:300] + "..." if len(str(action_res.output)) > 300 else str(action_res.output)
                    results.append(f"  ✓ {short}")
            return "\n".join(results)

        if not self._registry and not self._executor:
            return "No tool registry or executor available — cannot execute routine steps."

        from core.security.policy_engine import policy_engine
        from core.security.context import SecurityContext

        auto_ctx = SecurityContext(
            user_id=user_id,
            session_id=f"routine:{name}",
            interface_type="automation",
        )

        for i, step in enumerate(steps, 1):
            tool_name = step.get("tool", "")
            tool_args = step.get("args", {})
            approval_id = step.get("approval_id")

            results.append(f"Step {i}: {tool_name}")

            # 1. Zero-trust evaluation via PolicyEngine
            decision = policy_engine.evaluate_action(
                tool_name=tool_name,
                arguments=tool_args,
                user_id=user_id,
                session_id=f"routine:{name}",
                approval_id=approval_id,
            )

            if not decision.allowed:
                results.append(f"  ✖ Blocked by policy: {decision.reason}")
                continue

            # 2. Execution via ActionExecutor or Registry
            if self._executor:
                tool_func = None
                sec_level = SecurityLevel.SAFE
                if self._registry:
                    if hasattr(self._registry, "get_tool_func"):
                        tool_func = self._registry.get_tool_func(tool_name)
                    elif hasattr(self._registry, "get_tool"):
                        rt = self._registry.get_tool(tool_name)
                        if rt:
                            tool_func = rt.handler
                    if hasattr(self._registry, "get_security_level"):
                        sec_level = self._registry.get_security_level(tool_name)

                if tool_func is None:
                    results.append(f"  ⚠ Tool '{tool_name}' not found in registry — skipping")
                    continue

                try:
                    result = self._executor.execute(
                        tool_name=tool_name,
                        arguments=tool_args,
                        tool_func=tool_func,
                        security_level=sec_level,
                        approval_id=approval_id,
                        already_approved=bool(approval_id),
                        context=auto_ctx,
                    )
                    short = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
                    results.append(f"  ✓ {short}")
                except Exception as e:
                    results.append(f"  ✖ Error: {e}")

            elif self._registry:
                if hasattr(self._registry, "dispatch"):
                    ok, res = self._registry.dispatch(
                        tool_name=tool_name,
                        arguments=tool_args,
                        session_id=f"routine:{name}",
                        user_id=user_id,
                        approval_id=approval_id,
                        context=auto_ctx,
                    )
                    short = str(res)[:300] + "..." if len(str(res)) > 300 else str(res)
                    if ok:
                        results.append(f"  ✓ {short}")
                    else:
                        results.append(f"  ✖ Error: {short}")
                else:
                    # Legacy registry fallback: route strictly through centralized ActionExecutor
                    from core.action_executor import ActionExecutor
                    exec_inst = ActionExecutor()
                    tool_func = self._registry.get_tool_func(tool_name) if hasattr(self._registry, "get_tool_func") else None
                    if not tool_func:
                        results.append(f"  ⚠ Tool '{tool_name}' not found — skipping")
                        continue
                    try:
                        result = exec_inst.execute(
                            tool_name=tool_name,
                            arguments=tool_args,
                            tool_func=tool_func,
                            approval_id=approval_id,
                            already_approved=bool(approval_id),
                            context=auto_ctx,
                        )
                        short = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
                        results.append(f"  ✓ {short}")
                    except Exception as e:
                        results.append(f"  ✖ Error: {e}")

        results.append(f"\nRoutine '{name}' completed.")
        return "\n".join(results)


# ═══════════════════════════════════════════════════════════
#  Default Routines
# ═══════════════════════════════════════════════════════════

def _default_routines() -> dict:
    """Return built-in default routines."""
    return {
        "morning": {
            "description": "Morning briefing — weather, news, open dev tools",
            "steps": [
                {"tool": "get_weather", "args": {"city": "auto"}},
                {"tool": "get_news", "args": {"topic": "technology", "max_results": 3}},
                {"tool": "get_system_info", "args": {}},
                {"tool": "docker_list_containers", "args": {}},
                {"tool": "open_application", "args": {"name": "VS Code"}},
            ],
            "created": datetime.now().isoformat(),
        },
        "coding": {
            "description": "Start a coding session — open tools and check project",
            "steps": [
                {"tool": "open_application", "args": {"name": "VS Code"}},
                {"tool": "open_application", "args": {"name": "Windows Terminal"}},
                {"tool": "docker_list_containers", "args": {}},
                {"tool": "get_system_info", "args": {}},
            ],
            "created": datetime.now().isoformat(),
        },
        "goodnight": {
            "description": "End of day — save state and prepare shutdown",
            "steps": [
                {"tool": "get_system_info", "args": {}},
                {"tool": "docker_list_containers", "args": {}},
            ],
            "created": datetime.now().isoformat(),
        },
    }


# ═══════════════════════════════════════════════════════════
#  Module-level instance
# ═══════════════════════════════════════════════════════════

_engine: AutomationEngine | None = None


def _get_engine() -> AutomationEngine:
    global _engine
    if _engine is None:
        _engine = AutomationEngine()
    return _engine


# Tool functions for ToolRegistry
def run_routine(name: str) -> str:
    """Run a saved automation routine by name."""
    return _get_engine().run_routine(name)


def list_routines() -> str:
    """List all saved automation routines."""
    return _get_engine().list_routines()


def create_routine(name: str, description: str, steps: str) -> str:
    """Create a new automation routine. Steps should be a JSON array of tool calls."""
    try:
        parsed_steps = json.loads(steps) if isinstance(steps, str) else steps
        return _get_engine().create_routine(name, description, parsed_steps)
    except json.JSONDecodeError:
        return "Invalid steps format. Provide a JSON array of {\"tool\": ..., \"args\": ...} objects."


def delete_routine(name: str) -> str:
    """Delete a saved automation routine."""
    return _get_engine().delete_routine(name)


# ═══════════════════════════════════════════════════════════
#  Registration
# ═══════════════════════════════════════════════════════════

def register_all(registry):
    """Register all automation tools with a ToolRegistry."""
    from core.config import SecurityLevel
    global _engine
    _engine = AutomationEngine(tool_registry=registry)

    registry.register(
        name="run_routine",
        func=_engine.run_routine,
        description="Run a saved automation routine by name (e.g. 'morning', 'coding', 'goodnight')",
        params={
            "name": {"type": "string", "description": "Name of the routine to run"},
        },
        required=["name"],
        category="automation",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="list_routines",
        func=_engine.list_routines,
        description="List all saved automation routines",
        params={},
        category="automation",
        security_level=SecurityLevel.SAFE,
    )

    registry.register(
        name="create_routine",
        func=create_routine,
        description="Create a new automation routine with a name, description, and list of tool call steps",
        params={
            "name": {"type": "string", "description": "Routine name"},
            "description": {"type": "string", "description": "What this routine does"},
            "steps": {"type": "string", "description": "JSON array of steps, each with 'tool' and 'args' keys"},
        },
        required=["name", "description", "steps"],
        category="automation",
        security_level=SecurityLevel.MEDIUM,
    )

    registry.register(
        name="delete_routine",
        func=delete_routine,
        description="Delete a saved automation routine",
        params={
            "name": {"type": "string", "description": "Routine name to delete"},
        },
        required=["name"],
        category="automation",
        confirm=True,
        security_level=SecurityLevel.SENSITIVE,
    )

