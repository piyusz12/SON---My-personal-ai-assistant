# core/config.py — SON V3 Central Configuration & Security Policy
import os
from pathlib import Path
from enum import Enum


import logging
import logging.handlers

class SecurityLevel(Enum):
    """Permission levels for actions executed by SON."""
    SAFE = "safe"              # Read-only or harmless (e.g. search, check weather) -> Execute immediately
    MEDIUM = "medium"          # Reversible state changes (e.g. create folder, move file) -> Log & execute
    SENSITIVE = "sensitive"    # Destructive or system state (e.g. delete file, git commit) -> Require confirmation
    CRITICAL = "critical"      # High risk system actions (e.g. shutdown, format) -> Require explicit confirmation


class Config:
    """Central configuration repository containing system paths, model configs, and logging setup."""
    # ── Project Paths ──────────────────────────────────────────
    ROOT_DIR: Path = Path(__file__).parent.parent.resolve()
    PLUGINS_DIR: Path = ROOT_DIR / "plugins"
    CONFIG_DIR: Path = ROOT_DIR / "config"
    LOGS_DIR: Path = ROOT_DIR / "logs"
    MEMORY_DIR: Path = ROOT_DIR / "memory"
    SCREENSHOTS_DIR: Path = ROOT_DIR / "screenshots"

    # Ensure directories exist
    for d in [PLUGINS_DIR, CONFIG_DIR, LOGS_DIR, MEMORY_DIR, SCREENSHOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Logging Setup ──────────────────────────────────────────

    # Log file routing: logger name prefix → log file
    _LOG_ROUTES = {
        "son.performance": "performance.log",
        "son.tools": "tools.log",
        "son.conversations": "conversations.log",
    }

    # Loggers that should only write to file (no console spam)
    _SILENT_LOGGERS = {"son.performance", "son.tools", "son.conversations"}

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Returns a configured logger writing to both console and a rotating file."""
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # File Handler — main log
            log_file = Config.LOGS_DIR / "son.log"
            fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
            fh.setFormatter(formatter)
            logger.addHandler(fh)

            # Error-only File Handler — errors.log
            error_file = Config.LOGS_DIR / "errors.log"
            efh = logging.handlers.RotatingFileHandler(error_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
            efh.setLevel(logging.ERROR)
            efh.setFormatter(formatter)
            logger.addHandler(efh)
            
            # Console Handler (optional, could be removed for GUI)
            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)  # Only warnings+ to console to reduce noise
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            
        return logger

    @staticmethod
    def get_named_logger(name: str, log_category: str) -> logging.Logger:
        """
        Returns a logger that routes to a specific log file.
        
        Args:
            name: Logger name (e.g., 'son.tools').
            log_category: One of 'tools', 'performance', 'conversations', 'errors'.
        
        Returns:
            Configured logger writing to the category-specific log file.
        """
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            logger.propagate = False  # Don't bubble up to root

            # Map category to filename
            log_filenames = {
                "tools": "tools.log",
                "performance": "performance.log",
                "conversations": "conversations.log",
                "errors": "errors.log",
            }
            log_filename = log_filenames.get(log_category, "son.log")
            log_file = Config.LOGS_DIR / log_filename

            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10_000_000, backupCount=5, encoding='utf-8'
            )
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        return logger

    # ── LLM Models (Ollama) ────────────────────────────────────
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    MAIN_MODEL = os.getenv("SON_MAIN_MODEL", "qwen3:8b")
    CODING_MODEL = os.getenv("SON_CODING_MODEL", "qwen2.5-coder:7b")
    VISION_MODEL = os.getenv("SON_VISION_MODEL", "llama3.2-vision")
    EMBED_MODEL = os.getenv("SON_EMBED_MODEL", "nomic-embed-text")

    TEMPERATURE = 0.7
    CONTEXT_WINDOW = 4096         # reduced from 8192 — less history = faster inference
    LLM_STREAM = True
    MAX_TOOL_TURNS = 5

    # Ollama Performance Tuning (RTX 4060, 8GB VRAM)
    LLM_NUM_CTX = 4096            # context window size (tokens)
    LLM_NUM_GPU = 99              # force ALL layers to GPU
    LLM_NUM_PREDICT = 512         # cap max output tokens
    LLM_NUM_BATCH = 1024          # larger batch = faster prompt processing
    LLM_NUM_THREAD = 8            # match Ryzen 7 7840HS physical cores
    LLM_KEEP_ALIVE = "30m"        # keep model hot in VRAM

    # ── Speech & Audio Settings ───────────────────────────────
    WHISPER_MODEL = "large-v3"             # reverted to large-v3 for maximum accuracy
    WHISPER_DEVICE = "cuda"
    WHISPER_COMPUTE_TYPE = "float16"
    WHISPER_BEAM_SIZE = 1                   # greedy decoding = ~3x faster
    WHISPER_LANGUAGE = "en"
    WHISPER_VAD_FILTER = True               # skip silence segments

    PIPER_MODEL_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx"))
    PIPER_CONFIG_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx.json"))
    TTS_SAMPLE_RATE = 22050

    SAMPLE_RATE = 48000
    CHANNELS = 1
    AUDIO_DTYPE = "float32"
    MIC_DEVICE = None

    VAD_SILENCE_THRESHOLD = 0.015
    VAD_SILENCE_DURATION = 1.0            # reduced from 1.5s
    VAD_MIN_SPEECH_DURATION = 0.3         # reduced from 0.5s
    VAD_MAX_RECORD_DURATION = 30
    VAD_CHUNK_DURATION = 0.05             # 50ms chunks (was 100ms)

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
