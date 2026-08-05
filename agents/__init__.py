# agents/ — Agent Subsystems Init for SON V3
from agents.voice_agent import VoiceAgent
from agents.desktop_agent import DesktopAgent
from agents.memory_agent import MemoryAgent
from agents.terminal_agent import TerminalAgent
from agents.vision_agent import VisionAgent
from agents.internet_agent import InternetAgent

__all__ = [
    "VoiceAgent",
    "DesktopAgent",
    "MemoryAgent",
    "TerminalAgent",
    "VisionAgent",
    "InternetAgent",
]
