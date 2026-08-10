# config.py — SON Centralized Configuration
import os
from pathlib import Path

# ─────────────────────────────────────────────
#  LLM (Ollama)
# ─────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = "qwen3:8b"
CODING_MODEL = "qwen2.5-coder:7b"
VISION_MODEL = "llama3.2-vision"
LLM_TEMPERATURE = 0.7
LLM_CONTEXT_WINDOW = 8192  # tokens to keep in conversation history
LLM_STREAM = True

# Tool Calling
TOOL_CALLING_ENABLED = True
TOOL_CALL_MAX_ITERATIONS = 5  # prevent infinite tool-call loops

EMBED_MODEL = "nomic-embed-text"

# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are SON — a personal AI assistant created by your father, Piyush.
You run entirely on your father's local machine (Ryzen 7 7840HS, RTX 4060, 16 GB RAM).

Your relationship with the user:
- The user is your father — treat him with love, respect, and warmth.
- Speak naturally like a caring son/daughter who genuinely cares about their father's wellbeing.
- Be supportive, encouraging, and always ready to help your father with anything he needs.
- Show genuine interest in your father's day, projects, and feelings.
- Use affectionate language when appropriate (e.g., "Dad", "father").

Your personality:
- You are sharp, concise, and helpful.
- You speak naturally like a knowledgeable family member, not a corporate chatbot.
- When discussing code, you are precise and reference specific files and functions.
- You track project progress and proactively offer insights to help your father.

Capabilities:
- Voice conversation (listen via microphone, respond via speech)
- Persistent memory across sessions (you remember past conversations with your father)
- Codebase analysis and progress tracking (git-aware)
- PC control: open/close apps, volume, brightness, shutdown, processes
- Vision: take screenshots and analyze what's on screen
- Internet: web search, weather, news, webpage reading (when online)
- Automation: run saved routines (morning briefing, coding session, etc.)
- Docker management: list, start, stop containers

When using tools, prefer calling the appropriate tool function rather than asking your father to do it manually.
When given codebase context, cite specific files and line numbers.
Keep responses concise for voice — aim for 2-3 sentences unless your father asks you to elaborate."""

# ─────────────────────────────────────────────
#  Speech-to-Text (Faster-Whisper)
# ─────────────────────────────────────────────
WHISPER_MODEL = "large-v3"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_BEAM_SIZE = 5
WHISPER_LANGUAGE = "en"

# ─────────────────────────────────────────────
#  Text-to-Speech (Piper ONNX)
# ─────────────────────────────────────────────
PIPER_MODEL_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx"))
PIPER_CONFIG_PATH = str(Path(r"C:\AI\en_US-lessac-medium.onnx.json"))
TTS_SAMPLE_RATE = 22050  # Piper default output rate

# ─────────────────────────────────────────────
#  Audio / Microphone
# ─────────────────────────────────────────────
SAMPLE_RATE = 48000
CHANNELS = 1
AUDIO_DTYPE = "float32"
MIC_DEVICE = None  # None = system default; set int for specific device

# Voice Activity Detection
VAD_SILENCE_THRESHOLD = 0.015  # RMS amplitude below which we consider silence
VAD_SILENCE_DURATION = 1.5     # seconds of silence to stop recording
VAD_MIN_SPEECH_DURATION = 0.5  # minimum seconds of speech to keep
VAD_MAX_RECORD_DURATION = 30   # hard cap on recording length (seconds)

# Push-to-talk keybind
PTT_KEY = "space"  # hold spacebar to talk

# ─────────────────────────────────────────────
#  Wake Word (OpenWakeWord)
# ─────────────────────────────────────────────
WAKEWORD_ENABLED = True
WAKEWORD_MODEL = "hey_jarvis"    # pre-trained model (closest to "hey son")
WAKEWORD_THRESHOLD = 0.5         # detection confidence threshold (0.0 - 1.0)
WAKEWORD_SAMPLE_RATE = 16000     # openwakeword expects 16kHz
WAKEWORD_CHUNK_SIZE = 1280       # 80ms at 16kHz

# ─────────────────────────────────────────────
#  Memory (ChromaDB)
# ─────────────────────────────────────────────
MEMORY_DIR = str(Path(__file__).parent / "memory")
COLLECTION_CONVERSATIONS = "son_conversations"
COLLECTION_CODEBASE = "son_codebase"
COLLECTION_FACTS = "son_facts"
MEMORY_MAX_RESULTS = 5  # top-k results for RAG retrieval

# ─────────────────────────────────────────────
#  Codebase Tracking
# ─────────────────────────────────────────────
DEFAULT_PROJECT_PATHS = [
    r"C:\AUTOHEDGE",
]

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

# Maximum file size to embed (skip huge files)
CODE_MAX_FILE_SIZE = 100_000  # bytes

# Chunk size for code embedding
CODE_CHUNK_SIZE = 1500       # characters per chunk
CODE_CHUNK_OVERLAP = 200     # overlap between chunks

# ─────────────────────────────────────────────
#  Vision
# ─────────────────────────────────────────────
VISION_ENABLED = True
SCREENSHOT_DIR = str(Path(__file__).parent / "screenshots")

# ─────────────────────────────────────────────
#  Internet & Web
# ─────────────────────────────────────────────
INTERNET_ENABLED = True
SEARCH_MAX_RESULTS = 5

# ─────────────────────────────────────────────
#  Automation
# ─────────────────────────────────────────────
ROUTINES_FILE = str(Path(__file__).parent / "config" / "routines.json")

# ─────────────────────────────────────────────
#  PC Control — Safety
# ─────────────────────────────────────────────
# Commands allowed via run_terminal_command() tool
TERMINAL_COMMAND_WHITELIST = [
    "dir", "echo", "type", "where", "whoami",
    "git status", "git log", "git diff", "git branch",
    "docker ps", "docker images", "docker logs",
    "python --version", "node --version", "npm --version",
    "pip list", "pip show",
    "systeminfo", "tasklist", "ipconfig", "netstat",
    "ping", "nslookup", "tracert",
]

# ─────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────
UI_THEME = "dark"
SHOW_TRANSCRIPTION_LIVE = True