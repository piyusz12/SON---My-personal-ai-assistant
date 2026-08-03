# core/config.py — SON V3 Central Configuration & Security Policy
import os
from pathlib import Path
from enum import Enum


class SecurityLevel(Enum):
    """Permission levels for actions executed by SON."""
    SAFE = "safe"              # Read-only or harmless (e.g. search, check weather) -> Execute immediately
    MEDIUM = "medium"          # Reversible state changes (e.g. create folder, move file) -> Log & execute
    SENSITIVE = "sensitive"    # Destructive or system state (e.g. delete file, git commit) -> Require confirmation
    CRITICAL = "critical"      # High risk system actions (e.g. shutdown, format) -> Require explicit confirmation


class Config:
    # ── Project Paths ──────────────────────────────────────────
    ROOT_DIR = Path(__file__).parent.parent.resolve()
    PLUGINS_DIR = ROOT_DIR / "plugins"
    CONFIG_DIR = ROOT_DIR / "config"
    LOGS_DIR = ROOT_DIR / "logs"
    MEMORY_DIR = ROOT_DIR / "memory"
    SCREENSHOTS_DIR = ROOT_DIR / "screenshots"

    # Ensure directories exist
    for d in [PLUGINS_DIR, CONFIG_DIR, LOGS_DIR, MEMORY_DIR, SCREENSHOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # ── LLM Models (Ollama) ────────────────────────────────────
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    MAIN_MODEL = os.getenv("SON_MAIN_MODEL", "qwen3:8b")
    CODING_MODEL = os.getenv("SON_CODING_MODEL", "qwen2.5-coder:7b")
    VISION_MODEL = os.getenv("SON_VISION_MODEL", "llama3.2-vision")
    EMBED_MODEL = os.getenv("SON_EMBED_MODEL", "nomic-embed-text")

    TEMPERATURE = 0.7
    CONTEXT_WINDOW = 8192
    LLM_STREAM = True
    MAX_TOOL_TURNS = 5

    # ── Speech & Audio Settings ───────────────────────────────
    WHISPER_MODEL = "large-v3"
    WHISPER_DEVICE = "cuda"
    WHISPER_COMPUTE_TYPE = "float16"
    WHISPER_BEAM_SIZE = 5
    WHISPER_LANGUAGE = "en"

    PIPER_MODEL_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx"))
    PIPER_CONFIG_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx.json"))
    TTS_SAMPLE_RATE = 22050

    SAMPLE_RATE = 48000
    CHANNELS = 1
    AUDIO_DTYPE = "float32"
    MIC_DEVICE = None

    VAD_SILENCE_THRESHOLD = 0.015
    VAD_SILENCE_DURATION = 1.5
    VAD_MIN_SPEECH_DURATION = 0.5
    VAD_MAX_RECORD_DURATION = 30

    # ── Wake Word ──────────────────────────────────────────────
    WAKEWORD_ENABLED = True
    WAKEWORD_MODEL = "hey_jarvis"
    WAKEWORD_THRESHOLD = 0.5
    WAKEWORD_SAMPLE_RATE = 16000
    WAKEWORD_CHUNK_SIZE = 1280

    # ── System Control Whitelist ──────────────────────────────
    TERMINAL_COMMAND_WHITELIST = [
        "dir", "echo", "type", "where", "whoami",
        "git status", "git log", "git diff", "git branch",
        "docker ps", "docker images", "docker logs",
        "python --version", "node --version", "npm --version",
        "pip list", "pip show",
        "systeminfo", "tasklist", "ipconfig", "netstat",
        "ping", "nslookup", "tracert",
    ]

    DEFAULT_PROJECT_PATHS = [
        r"C:\AUTOHEDGE",
        str(ROOT_DIR),
    ]

    # Security confirmation toggle
    AUTO_CONFIRM_SAFE = True
    REQUIRE_CONFIRM_SENSITIVE = True
    REQUIRE_CONFIRM_CRITICAL = True
