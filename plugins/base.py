from abc import ABC, abstractmethod
from typing import Callable
from core.config import SecurityLevel


class BasePlugin(ABC):
    """
    Abstract base class for all SON V3 plugins.
    Each plugin defines callable tools with assigned Security Levels.
    """

    def __init__(self, name: str, description: str, category: str = "general"):
        self.name = name
        self.description = description
        self.category = category
        self.tools: dict[str, dict] = {}

    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str,
        params: dict[str, dict] | None = None,
        required: list[str] | None = None,
        security_level: SecurityLevel = SecurityLevel.SAFE
    ):
        """Register a tool exposed by this plugin."""
        self.tools[name] = {
            "func": func,
            "description": description,
            "params": params or {},
            "required": required or [],
            "security_level": security_level,
            "category": self.category,
            "plugin": self.name,
        }

    @abstractmethod
    def initialize(self):
        """Plugin-specific initialization."""
        pass
