# tools/registry.py — Tool Registry & Dispatch for SON
"""
Manages tool registration, schema generation, and dispatch.
Tools are Python functions that the LLM can invoke via Ollama's function calling.

Usage:
    registry = ToolRegistry()

    @registry.tool(description="Get system info", params={...})
    def get_system_info():
        ...

    # Or register manually:
    registry.register("get_weather", get_weather, description=..., params=...)

    # Get Ollama-compatible tool definitions:
    tool_defs = registry.to_ollama_tools()

    # Dispatch a tool call from the LLM:
    result = registry.call("get_weather", {"city": "Mumbai"})
"""
import json
import traceback
from typing import Callable, Any

from core.config import SecurityLevel


class ToolRegistry:
    """
    Central registry for all tools SON can use.
    Handles registration, schema generation, and safe dispatch.
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}

    # ── Registration ──────────────────────────────────────────

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        params: dict[str, dict] | None = None,
        required: list[str] | None = None,
        category: str = "general",
        confirm: bool = False,
        security_level: SecurityLevel = SecurityLevel.SAFE,
    ):
        """
        Register a tool function.

        Args:
            name: Unique tool name (e.g. "open_application").
            func: The Python function to call.
            description: Human-readable description for the LLM.
            params: Dict of param_name -> {"type": ..., "description": ...}.
            required: List of required parameter names.
            category: Category for grouping (e.g. "system", "web").
            confirm: If True, ask user confirmation before executing.
            security_level: SecurityLevel for this tool (SAFE/MEDIUM/SENSITIVE/CRITICAL).
        """
        self._tools[name] = {
            "func": func,
            "description": description,
            "params": params or {},
            "required": required or [],
            "category": category,
            "confirm": confirm,
            "security_level": security_level,
        }

    def tool(
        self,
        name: str | None = None,
        description: str = "",
        params: dict[str, dict] | None = None,
        required: list[str] | None = None,
        category: str = "general",
        confirm: bool = False,
        security_level: SecurityLevel = SecurityLevel.SAFE,
    ):
        """Decorator for registering a tool function."""
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self.register(
                name=tool_name,
                func=func,
                description=description or func.__doc__ or "",
                params=params,
                required=required,
                category=category,
                confirm=confirm,
                security_level=security_level,
            )
            return func
        return decorator

    # ── Schema Generation ─────────────────────────────────────

    def to_ollama_tools(self) -> list[dict]:
        """
        Convert all registered tools to Ollama's tool format.
        Returns a list of tool definition dicts compatible with ollama.chat(tools=...).
        """
        tools = []
        for name, tool in self._tools.items():
            # Build JSON Schema for parameters
            properties = {}
            for param_name, param_info in tool["params"].items():
                prop = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
                if "enum" in param_info:
                    prop["enum"] = param_info["enum"]
                if "default" in param_info:
                    prop["default"] = param_info["default"]
                properties[param_name] = prop

            tool_def = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": tool["required"],
                    },
                },
            }
            tools.append(tool_def)

        return tools

    # ── Dispatch ──────────────────────────────────────────────

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """
        Execute a registered tool by name.

        Args:
            name: Tool name.
            arguments: Dict of arguments to pass.

        Returns:
            String result (success or error message).
        """
        if name not in self._tools:
            return f"Error: Unknown tool '{name}'. Available: {', '.join(self._tools.keys())}"

        tool = self._tools[name]
        args = arguments or {}

        try:
            result = tool["func"](**args)
            # Ensure result is a string for the LLM
            if result is None:
                return "Done."
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2, default=str)
            return str(result)
        except Exception as e:
            tb = traceback.format_exc()
            return f"Error executing '{name}': {e}\n{tb}"

    def needs_confirmation(self, name: str) -> bool:
        """Check if a tool requires user confirmation before execution."""
        if name in self._tools:
            return self._tools[name].get("confirm", False)
        return False

    def get_security_level(self, name: str) -> SecurityLevel:
        """Get the security level of a registered tool."""
        if name in self._tools:
            return self._tools[name].get("security_level", SecurityLevel.SAFE)
        return SecurityLevel.SAFE

    def get_tool_func(self, name: str) -> Callable | None:
        """Get the callable function for a tool."""
        if name in self._tools:
            return self._tools[name]["func"]
        return None

    # ── Introspection ─────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """List all registered tools with their metadata."""
        return [
            {
                "name": name,
                "description": tool["description"],
                "category": tool["category"],
                "params": list(tool["params"].keys()),
                "confirm": tool["confirm"],
            }
            for name, tool in self._tools.items()
        ]

    def get_tool_names(self) -> list[str]:
        """Return all tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def count(self) -> int:
        return len(self._tools)

    def get_categories(self) -> dict[str, list[str]]:
        """Group tool names by category."""
        cats: dict[str, list[str]] = {}
        for name, tool in self._tools.items():
            cat = tool["category"]
            cats.setdefault(cat, []).append(name)
        return cats
