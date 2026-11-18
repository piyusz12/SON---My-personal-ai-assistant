"""SON core package.

Keep package import deliberately lightweight. Most SON modules import
``core.config``; importing the entire host, memory, audio, and model stack at
that point made simple commands fail whenever an optional integration was
unavailable. Public runtime objects remain available through lazy imports.
"""

from importlib import import_module

from core.config import Config, SecurityLevel

__all__ = [
    "Config", "SecurityLevel", "SystemState", "IntentRouter", "Brain",
    "Pipeline", "GPUManager", "EmbeddingCache", "CodeChunkCache",
    "HostAgent", "host_agent", "EventBus", "event_bus", "EventType",
    "SonEvent",
]

_LAZY_EXPORTS = {
    "SystemState": ("core.state", "SystemState"),
    "IntentRouter": ("core.router", "IntentRouter"),
    "Brain": ("core.brain", "Brain"),
    "Pipeline": ("core.pipeline", "Pipeline"),
    "GPUManager": ("core.gpu_manager", "GPUManager"),
    "EmbeddingCache": ("core.cache", "EmbeddingCache"),
    "CodeChunkCache": ("core.cache", "CodeChunkCache"),
    "HostAgent": ("core.host_agent", "HostAgent"),
    "host_agent": ("core.host_agent", "host_agent"),
    "EventBus": ("core.event_bus", "EventBus"),
    "event_bus": ("core.event_bus", "event_bus"),
    "EventType": ("core.event_bus", "EventType"),
    "SonEvent": ("core.event_bus", "SonEvent"),
}


def __getattr__(name: str):
    """Load heavyweight components only when a caller actually needs them."""
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
