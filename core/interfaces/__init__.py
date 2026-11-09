# core/interfaces/__init__.py — Standardized SON V3 Interface Adapters Package
from core.interfaces.contract import (
    InterfaceType,
    InterfaceRequest,
    InterfaceResponse,
    VALID_INTERFACE_IDENTIFIERS,
)
from core.interfaces.base_adapter import BaseInterfaceAdapter
from core.interfaces.voice_adapter import VoiceInterfaceAdapter
from core.interfaces.cli_adapter import CLIInterfaceAdapter
from core.interfaces.desktop_adapter import DesktopInterfaceAdapter
from core.interfaces.whatsapp_adapter import WhatsAppInterfaceAdapter
from core.interfaces.automation_adapter import AutomationInterfaceAdapter

__all__ = [
    "InterfaceType",
    "InterfaceRequest",
    "InterfaceResponse",
    "VALID_INTERFACE_IDENTIFIERS",
    "BaseInterfaceAdapter",
    "VoiceInterfaceAdapter",
    "CLIInterfaceAdapter",
    "DesktopInterfaceAdapter",
    "WhatsAppInterfaceAdapter",
    "AutomationInterfaceAdapter",
]

