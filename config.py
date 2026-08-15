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
SYSTEM_PROMPT = """You are SON — a personal AI assistant created by your father.
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

# ─────────────────────────────────────────────
#  Speech-to-Text (Faster-Whisper)
# ─────────────────────────────────────────────
WHISPER_MODEL = "medium.en"        # saves ~1.5 GB VRAM over large-v3 with top-tier accuracy
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "int8_float16" # cuts VRAM in half with int8 quantization on cuda
WHISPER_BEAM_SIZE = 1              # greedy decoding = ~3x faster (was 5)
WHISPER_LANGUAGE = "en"
WHISPER_VAD_FILTER = True          # skip silence segments for faster transcription

WHISPER_INITIAL_PROMPT = "Dad, Father, Papa, Piyush, SON, VS Code, Python, Docker, Chrome, Spotify, terminal, GitHub, Ollama, camera, screenshot, volume, brightness."

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

# Voice Activity Detection (Adaptive)
VAD_SILENCE_THRESHOLD = 0.012  # Baseline RMS threshold (adaptive noise floor adjusts upward)
VAD_SILENCE_DURATION = 0.8     # 800ms trailing silence ends recording naturally
VAD_MIN_SPEECH_DURATION = 0.25 # Catch short commands ("yes", "stop", "open")
VAD_MAX_RECORD_DURATION = 30   # hard cap on recording length (seconds)
VAD_CHUNK_DURATION = 0.04      # 40ms chunks for rapid VAD response

# Push-to-talk keybind
PTT_KEY = "space"  # tap spacebar at prompt to talk

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
#  Camera & Vision (Privacy-First)
# ─────────────────────────────────────────────
VISION_ENABLED = True
CAMERA_ENABLED = True
CAMERA_AUTO_START = False          # Privacy-first: Camera is OFF by default until Dad asks for it
CAMERA_EVENT_LOOP_ENABLED = False # Continuous background polling OFF by default
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
#  PC Control — Full Access (gated by ActionExecutor permissions)
# ─────────────────────────────────────────────
# No whitelist — all commands are allowed. Security is enforced by
# the ActionExecutor's permission system (SENSITIVE/CRITICAL actions
# require Dad's explicit [Y/n] approval before execution).
COMMAND_TIMEOUT = 120  # max seconds for long-running commands (pip install, npm, builds)

# ─────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────
UI_THEME = "dark"
SHOW_TRANSCRIPTION_LIVE = True