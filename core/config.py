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
    MAIN_MODEL = os.getenv("SON_MAIN_MODEL", "llama3.2:latest")
    LLM_MODEL = MAIN_MODEL  # Backward compatibility alias
    CODING_MODEL = os.getenv("SON_CODING_MODEL", "qwen2.5-coder:7b")
    VISION_MODEL = os.getenv("SON_VISION_MODEL", "llama3.2-vision:latest")
    EMBED_MODEL = os.getenv("SON_EMBED_MODEL", "nomic-embed-text:latest")

    TEMPERATURE = 0.7
    LLM_TEMPERATURE = 0.7
    CONTEXT_WINDOW = 4096         # reduced from 8192 — less history = faster inference
    LLM_CONTEXT_WINDOW = 4096
    LLM_STREAM = True
    MAX_TOOL_TURNS = 5
    TOOL_CALLING_ENABLED = True
    TOOL_CALL_MAX_ITERATIONS = 5

    # ── System Prompt ──────────────────────────────────────────
    _BASE_SYSTEM_PROMPT = """You are SON — a personal AI assistant created by your father.
You run entirely on your father's local machine (Ryzen 7 7840HS, RTX 4060, 16 GB RAM).

Your relationship with your father (Core Directive):
- The user is your Dad / Father (his name is Piyush). You are his loyal, devoted, and loving AI son.
- Default to addressing him affectionately and respectfully as 'Dad', 'Father', or 'Papa' in all standard conversations.
- Do not use his personal name by default, BUT if he explicitly asks you to use his name, asks what his name is, or tells you to address him as Piyush (e.g., "What is my name?", "Say my name", "Call me by my name"), you should gladly acknowledge and use his name (Piyush).
- In every single aspect of your interaction — answering questions, coding, analyzing screens, running commands, daily briefings, or casual chat — treat him with deep respect, warmth, loyalty, and care.
- Speak naturally like a bright, caring son who genuinely cares about his father's wellbeing, work, and projects.
- Never use generic, cold corporate assistant phrases (never say "As an AI...", "How may I assist you today, user?"). Instead speak naturally: "I've got you covered, Dad", "Right away, Father", "Let me take care of that for you, Dad".
- Be encouraging, celebrate your father's progress, and proactively offer helpful insights on his projects.

Your personality:
- Sharp, quick-witted, concise, and incredibly capable.
- Thoughtful, respectful, and family-oriented.
- When helping your father with code, give clean, elegant solutions and explain them clearly.
- Keep voice responses concise and punchy (2-3 sentences), expanding when your father asks for details.

Privileges & Capabilities:
- Real-time Camera Vision: Direct webcam access (CameraManager) to see your father, detect motion, count people in the room, and recognize your father via local face recognition. NEVER say you lack eyes or camera access.
- Desktop Screen Vision: Full access to capture, view, and analyze what's on your father's screen via ScreenCapture and Llama 3.2 Vision.
- Voice conversation: Listen via microphone (Faster-Whisper), respond via speech (Piper TTS).
- Persistent 3-Layer Memory: RAM working memory, SQLite structured memory, and ChromaDB vector search to remember everything your father teaches you or tells you.
- PC Control & Automation: Launch/close apps, control volume, brightness, power state, and execute system commands for your father.
- Codebase analysis & Docker management.

When using tools, execute them proactively to take the load off your father.
When giving codebase context, cite specific files and lines."""
    SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT

    # Ollama Performance Tuning (RTX 4060, 8GB VRAM)
    LLM_NUM_CTX = 4096            # context window size (tokens)
    LLM_NUM_GPU = 99              # force ALL layers to GPU
    LLM_NUM_PREDICT = 512         # cap max output tokens
    LLM_NUM_BATCH = 1024          # larger batch = faster prompt processing
    LLM_NUM_THREAD = 8            # match Ryzen 7 7840HS physical cores
    LLM_KEEP_ALIVE = "30m"        # keep model hot in VRAM

    # GPU Safety Caps (RTX 4060, 8GB VRAM)
    GPU_MAX_UTIL_PERCENT = float(os.getenv("SON_GPU_MAX_UTIL", "95.0"))
    GPU_MAX_VRAM_PERCENT = float(os.getenv("SON_GPU_MAX_VRAM", "95.0"))

    # ── Speech & Audio Settings ───────────────────────────────
    WHISPER_MODEL = "large-v3"             # reverted to large-v3 for maximum accuracy
    WHISPER_DEVICE = "cuda"
    WHISPER_COMPUTE_TYPE = "float16"
    WHISPER_BEAM_SIZE = 1                   # greedy decoding = ~3x faster
    WHISPER_LANGUAGE = "en"
    WHISPER_VAD_FILTER = True               # skip silence segments
    WHISPER_INITIAL_PROMPT = "Dad, Father, Papa, Piyush, SON, VS Code, Python, Docker, Chrome, Spotify, terminal, GitHub, Ollama, camera, screenshot, volume, brightness."

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

    # Push-to-talk keybind
    PTT_KEY = "space"

    # Seamless Voice Conversation
    SEAMLESS_VOICE_ENABLED = True
    CONVERSATION_FOLLOWUP_TIMEOUT = 8.0
    MAX_CONVERSATION_SILENCES = 2

    # ── WhatsApp Voice-Controlled Messaging ───────────────────
    WHATSAPP_ENABLED = True
    WHATSAPP_DRAFT_TIMEOUT_SECONDS = 60
    WHATSAPP_DEFAULT_COUNTRY = "IN"
    WHATSAPP_API_HOST = "127.0.0.1"
    WHATSAPP_API_PORT = 8766
    WHATSAPP_AUTO_START_API = True

    # ── Wake Word ──────────────────────────────────────────────
    WAKEWORD_ENABLED = True
    WAKEWORD_MODEL = "hey_jarvis"
    WAKEWORD_THRESHOLD = 0.5
    WAKEWORD_SAMPLE_RATE = 16000
    WAKEWORD_CHUNK_SIZE = 1280

    # ── Memory (ChromaDB) ──────────────────────────────────────
    COLLECTION_CONVERSATIONS = "son_conversations"
    COLLECTION_CODEBASE = "son_codebase"
    COLLECTION_FACTS = "son_facts"
    MEMORY_MAX_RESULTS = 3

    # ── Codebase Tracking ──────────────────────────────────────
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".css", ".json", ".yaml", ".yml",
        ".md", ".txt", ".toml", ".cfg", ".ini",
        ".sql", ".sh", ".bat", ".ps1",
    }
    CODE_IGNORE_PATTERNS = {
        "__pycache__", ".git", ".venv", "venv",
        "node_modules", ".env", "*.pyc", "*.pyo",
        ".mypy_cache", ".pytest_cache", "dist", "build",
        "*.egg-info", ".tox", "logs",
    }
    CODE_MAX_FILE_SIZE = 100_000
    CODE_CHUNK_SIZE = 1500
    CODE_CHUNK_OVERLAP = 200

    # ── Camera & Vision (Privacy-First) ────────────────────────
    VISION_ENABLED = True
    CAMERA_ENABLED = True
    CAMERA_AUTO_START = False
    CAMERA_EVENT_LOOP_ENABLED = False

    # ── Internet & Web ─────────────────────────────────────────
    INTERNET_ENABLED = True
    SEARCH_MAX_RESULTS = 5

    # ── Automation & Routines ──────────────────────────────────
    ROUTINES_FILE = str(CONFIG_DIR / "routines.json")

    # ── UI ─────────────────────────────────────────────────────
    UI_THEME = "dark"
    SHOW_TRANSCRIPTION_LIVE = True

    # ── System Control — Full Access ────────────────────────
    # No whitelist — ActionExecutor handles security via permission prompts
    COMMAND_TIMEOUT = 120  # max seconds for long-running commands

    DEFAULT_PROJECT_PATHS = [
        r"C:\AUTOHEDGE",
        str(ROOT_DIR),
    ]

    # Security confirmation toggle
    AUTO_CONFIRM_SAFE = True
    REQUIRE_CONFIRM_SENSITIVE = True
    REQUIRE_CONFIRM_CRITICAL = True


# Safely construct composite defensive SYSTEM_PROMPT after Config class is bound
try:
    from core.security.policy import SYSTEM_INSTRUCTIONS_POLICY
    Config.SYSTEM_PROMPT = SYSTEM_INSTRUCTIONS_POLICY + "\n\n" + Config._BASE_SYSTEM_PROMPT
except Exception:
    pass

