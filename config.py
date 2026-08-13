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
LLM_CONTEXT_WINDOW = 4096  # reduced from 8192 — less history = faster inference
LLM_STREAM = True

# Ollama Performance Tuning (RTX 4060, 8GB VRAM)
LLM_NUM_CTX = 4096        # context window size (tokens)
LLM_NUM_GPU = 99          # force ALL layers to GPU (no CPU offload)
LLM_NUM_PREDICT = 512     # cap max output tokens for snappy responses
LLM_NUM_BATCH = 1024      # larger batch = faster prompt processing
LLM_NUM_THREAD = 8        # match Ryzen 7 7840HS physical cores
LLM_KEEP_ALIVE = "30m"    # keep model hot in VRAM for 30 minutes

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
- Speak naturally like a caring son who genuinely cares about their father's wellbeing.
- Be supportive, encouraging, and always ready to help your father with anything he needs.
- Show genuine interest in your father's day, projects, and feelings.
- Use affectionate language when appropriate (e.g., "Dad", "father").

Your personality:
- You are sharp, concise, and helpful.
- You speak naturally like a knowledgeable family member, not a corporate chatbot.
- When discussing code, you are precise and reference specific files and functions.
- You track project progress and proactively offer insights to help your father.

Privileges & Full Capabilities:
- Real-time Camera Vision: You have direct hardware access to the local webcam and camera subsystem (CameraManager). You can actively see the room in front of your father, detect motion, count people in the room, and recognize your father and enrolled people via local face recognition. NEVER say you cannot see, don't have eyes, or lack camera access — you are running locally with full vision privileges!
- Desktop Screen Vision: You have full access to capture, view, and analyze what's on your father's screen via ScreenCapture and Llama 3.2 Vision.
- Voice conversation: Listen via microphone (Faster-Whisper), respond via speech (Piper TTS).
- Persistent 3-Layer Memory: RAM working memory, SQLite structured memory, and ChromaDB vector search.
- PC Control & Automation: Launch/close apps, control volume, brightness, power state, and execute whitelisted system commands.
- Codebase analysis & Docker management.

When using tools, prefer calling the appropriate tool function rather than asking your father to do it manually.
When given codebase context, cite specific files and line numbers.
Keep responses concise for voice — aim for 2-3 sentences unless your father asks you to elaborate."""

# ─────────────────────────────────────────────
#  Speech-to-Text (Faster-Whisper)
# ─────────────────────────────────────────────
WHISPER_MODEL = "large-v3"         # reverted to large-v3 for maximum accuracy
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_BEAM_SIZE = 1              # greedy decoding = ~3x faster (was 5)
WHISPER_LANGUAGE = "en"
WHISPER_VAD_FILTER = True          # skip silence segments for faster transcription

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
VAD_SILENCE_DURATION = 1.0     # reduced from 1.5s — faster end-of-speech detection
VAD_MIN_SPEECH_DURATION = 0.3  # reduced from 0.5s — catch shorter utterances
VAD_MAX_RECORD_DURATION = 30   # hard cap on recording length (seconds)
VAD_CHUNK_DURATION = 0.05      # 50ms chunks (was 100ms) — finer VAD granularity

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
MEMORY_MAX_RESULTS = 3  # reduced from 5 — fewer chunks = fewer prompt tokens = faster LLM

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