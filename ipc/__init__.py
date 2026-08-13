# ipc/__init__.py — SON IPC Package
from ipc.protocol import IPCMessage, EventType, VisualState
from ipc.server import SONIPCServer

__all__ = ["IPCMessage", "EventType", "VisualState", "SONIPCServer"]
