import json
import traceback
from typing import Any
from plugins.base import BasePlugin


class PluginRegistry:
    """
    Central registry for loading and executing SON V3 plugins.
    Converts registered plugin tools into Ollama-compatible JSON schemas.
    """

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._tools: dict[str, dict] = {}

    def register_plugin(self, plugin: BasePlugin):
        """Register a plugin instance."""
        plugin.initialize()
        self._plugins[plugin.name] = plugin
        for tool_name, tool_info in plugin.tools.items():
            self._tools[tool_name] = tool_info

    def to_ollama_tools(self) -> list[dict]:
        """Convert registered tools into Ollama tool schemas."""
        from tools.registry import format_tools_dict_to_ollama
        return format_tools_dict_to_ollama(self._tools)

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Execute a tool by name."""
        if name not in self._tools:
            return f"Error: Unknown tool '{name}'."

        tool = self._tools[name]
        args = arguments or {}

        try:
            res = tool["func"](**args)
            if res is None:
                return "Done."
            if isinstance(res, (dict, list)):
                return json.dumps(res, indent=2, default=str)
            return str(res)
        except Exception as e:
            tb = traceback.format_exc()
            return f"Error executing '{name}': {e}\n{tb}"

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool_meta(self, name: str) -> dict:
        return self._tools.get(name, {})

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": meta["description"],
                "category": meta["category"],
                "security_level": meta["security_level"].value,
                "plugin": meta["plugin"],
            }
            for name, meta in self._tools.items()
        ]

    def count(self) -> int:
        return len(self._tools)


__all__ = ["PluginRegistry"]
