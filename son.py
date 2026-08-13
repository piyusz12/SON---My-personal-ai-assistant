# son.py — SON Personal AI Assistant (Main Orchestrator)
"""
SON — Personal AI Assistant
Listen • Think • Speak • Remember • See • Control • Automate
import logging
from core.config import Config
logger = Config.get_logger(__name__)


Usage:
    python son.py              Start SON in interactive mode
    python son.py --voice      Start in voice-first mode
    python son.py --wakeword   Start with wake word detection ("Hey SON")
    python son.py --scan       Scan codebases on startup
"""
import sys
import os
import threading
import argparse

# Fix Windows console encoding (cp1252 can't handle Unicode/emoji)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ── Local Modules ─────────────────────────────────────────
import config
from ui import TerminalUI
from memory import Memory
from memory.manager import MemoryManager
from brain import Brain
from codebase import CodeTracker
from commands import CommandHandler
from audio import AudioManager
from stt import SpeechToText
from tts import TextToSpeech
from tools import ToolRegistry
from core.intent_router import IntentRouter, IntentType
from core.health import HealthMonitor
from core.profiler import RequestTracer


class Son:
    """
    Main orchestrator that ties all components together.
    Runs the conversation loop: Listen → Understand → Think → Speak.
    """

    def __init__(self, voice_mode: bool = False, scan_on_start: bool = False,
                 wakeword_mode: bool = False):
        self._voice_mode = voice_mode
        self._scan_on_start = scan_on_start
        self._wakeword_mode = wakeword_mode
        self._running = False

        # UI (initialize first for status updates)
        self.ui = TerminalUI()

        # Core modules (lazy-loaded where possible)
        self.memory = None
        self.memory_manager = None
        self.brain = None
        self.codebase = None
        self.commands = None
        self.router = IntentRouter()
        self.health = HealthMonitor()
        self.camera = None
        self.vision_loop = None
        self.audio = None
        self.stt = None
        self.tts = None
        self.tools = None
        self.wakeword = None
        self.vision = None

        # Wake word event
        self._wake_event = threading.Event()

    # ── Initialization ────────────────────────────────────────

    def _init_all(self):
        """Initialize all modules with PARALLEL loading for faster startup."""
        self.ui.show_banner()

        # 1. Tool Registry (must be first — other modules register into it)
        self.ui.update_status("Setting up tool registry...")
        self.tools = ToolRegistry()

        # 2. Parallel initialization of independent modules
        #    Memory, Audio, STT, TTS can all load concurrently
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _init_memory():
            return Memory()

        def _init_audio():
            return AudioManager()

        def _init_stt():
            stt = SpeechToText(eager_load=True)  # Eager load Whisper into GPU
            return stt

        def _init_tts():
            tts = TextToSpeech(eager_load=True)   # Eager load Piper model
            return tts

        self.ui.update_status("Loading modules in parallel...")
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="son-init") as pool:
            future_memory = pool.submit(_init_memory)
            future_audio = pool.submit(_init_audio)
            future_stt = pool.submit(_init_stt)
            future_tts = pool.submit(_init_tts)

            # Collect results as they complete
            self.memory = future_memory.result()
            self.memory_manager = MemoryManager(semantic_memory=self.memory)
            self.ui.update_status("  ✓ 3-Layer Memory (RAM + SQLite + ChromaDB)")

            self.audio = future_audio.result()
            self.ui.update_status("  ✓ Audio manager")

            self.stt = future_stt.result()
            self.ui.update_status("  ✓ STT (Whisper — eager loaded)")

            self.tts = future_tts.result()
            self.ui.update_status("  ✓ TTS (Piper ONNX)")

        # 3. Codebase (depends on memory)
        self.ui.update_status("Loading codebase tracker...")
        self.codebase = CodeTracker(memory=self.memory)

        # 4. Register tools (before Brain so Brain can use them)
        self.ui.update_status("Registering tools...")
        self._register_all_tools()

        # 5. Brain (LLM + Tool Calling + Resilient Client)
        self.ui.update_status("Loading brain (Qwen3 + Resilient Client)...")
        self.brain = Brain(
            memory=self.memory,
            codebase=self.codebase,
            tools=self.tools,
        )

        # 6. Commands (pattern-matched, bypass LLM)
        self.ui.update_status("Loading command handler & intent router...")
        self.commands = CommandHandler(
            memory=self.memory,
            codebase=self.codebase,
            brain=self.brain,
            ui=self.ui,
            tool_registry=self.tools,
        )

        # 7. Camera Vision Subsystem (first-class)
        self.ui.update_status("Initializing Camera Vision & Privacy Subsystem...")
        try:
            from vision.camera.capture import CameraManager
            from vision.camera.events import VisionEventLoop
            self.camera = CameraManager()
            self.camera.start()
            self.vision_loop = VisionEventLoop(
                camera_manager=self.camera,
                structured_memory=self.memory_manager.structured,
            )
            self.vision_loop.start()
            self.ui.update_status("  ✓ Camera Subsystem & Vision Event Loop Active")
        except Exception as e:
            self.ui.update_status(f"  ⚠ Camera Subsystem unavailable: {e}")

        # 8. Screen Vision (Desktop Visual Analysis)
        if config.VISION_ENABLED:
            self.ui.update_status("Loading Screen Vision (Llama 3.2 Vision)...")
            try:
                from vision.screen.analysis import ScreenAnalyzer
                self.vision = ScreenAnalyzer(brain=self.brain)
            except Exception as e:
                self.ui.update_status(f"Screen Vision unavailable: {e}")

        # 9. Wake word (optional)
        if self._wakeword_mode and config.WAKEWORD_ENABLED:
            self.ui.update_status("Loading wake word detector...")
            try:
                from wakeword import WakeWordListener
                self.wakeword = WakeWordListener(on_wake=self._on_wake_detected)
            except ImportError as e:
                self.ui.update_status(f"Wake word unavailable: {e}")

        # 10. Pre-warm Ollama — ensure model is loaded in VRAM before first query
        self.ui.update_status("Pre-warming Ollama (loading model to GPU)...")
        try:
            from core.ollama_client import ResilientOllamaClient
            client = ResilientOllamaClient(host=config.OLLAMA_HOST)
            client.ensure_model_loaded(config.LLM_MODEL)
            self.ui.update_status("  ✓ Ollama model hot in VRAM")
        except Exception as e:
            self.ui.update_status(f"  ⚠ Ollama pre-warm failed: {e}")

        # 11. Start Health Monitor
        self.health.start_monitoring()

        # Show startup info
        stats = self.memory_manager.stats()
        tool_count = self.tools.count()
        self.ui.show_startup_info_extended(stats, tool_count)

        # Optional: scan codebases on start
        if self._scan_on_start:
            self._initial_scan()

    def _register_all_tools(self):
        """Register all tool modules and V3 plugins with central ToolRegistry."""
        # Legacy tools
        try:
            from tools.windows_control import register_all as reg_win
            from tools.docker_control import register_all as reg_doc
            from tools.web import register_all as reg_web
            from tools.automation import register_all as reg_auto
            reg_win(self.tools)
            reg_doc(self.tools)
            reg_web(self.tools)
            reg_auto(self.tools)
        except Exception as e:
            logger.error(f"Exception caught: {e}", exc_info=True)

        # V3 Plugins
        try:
            from plugins.windows import WindowsPlugin
            from plugins.files import FilesPlugin
            from plugins.vscode import VSCodePlugin
            from plugins.docker import DockerPlugin
            from plugins.browser import BrowserPlugin
            from plugins.spotify import SpotifyPlugin
            from plugins.weather import WeatherPlugin

            for plugin_cls in [WindowsPlugin, FilesPlugin, VSCodePlugin, DockerPlugin, BrowserPlugin, SpotifyPlugin, WeatherPlugin]:
                p = plugin_cls()
                p.initialize()
                for t_name, t_info in p.tools.items():
                    if not self.tools.has_tool(t_name):
                        self.tools.register(
                            name=t_name,
                            func=t_info["func"],
                            description=t_info["description"],
                            params=t_info["params"],
                            required=t_info["required"],
                            category=t_info["category"]
                        )
            self.ui.update_status("  ✓ SON V3 Plugin Matrix (34 tools)")
        except Exception as e:
            self.ui.update_status(f"  ✗ V3 Plugins: {e}")

    def _initial_scan(self):
        """Scan configured projects on startup."""
        self.ui.update_status("Scanning codebases...")
        for proj in config.DEFAULT_PROJECT_PATHS:
            from pathlib import Path
            name = Path(proj).name
            self.ui.update_status(f"Indexing {name}...")
            try:
                stats = self.codebase.scan(proj)
                self.ui.update_status(
                    f"{name}: {stats['files_scanned']} files, "
                    f"{stats['chunks_embedded']} chunks"
                )
            except Exception as e:
                self.ui.show_error(f"Failed to scan {name}: {e}")

    # ── Wake Word ─────────────────────────────────────────────

    def _on_wake_detected(self):
        """Callback fired when wake word is detected."""
        self._wake_event.set()

    # ── Input Handling ────────────────────────────────────────

    def _get_voice_input(self) -> str | None:
        """Record and transcribe voice input."""
        self.ui.show_listening()

        # Pause wake word while recording
        if self.wakeword and self.wakeword.is_listening:
            self.wakeword.pause()

        audio = self.audio.record_vad()

        # Resume wake word
        if self._wakeword_mode and self.wakeword:
            self.wakeword.resume()

        if audio is None:
            return None

        self.ui.update_status("Transcribing...")
        text = self.stt.transcribe(audio, sample_rate=config.SAMPLE_RATE)

        if text and text.strip():
            self.ui.show_transcription(text.strip())
            return text.strip()

        return None

    def _get_input(self) -> str | None:
        """
        Get user input — voice, keyboard, or wake word triggered.
        """
        # Wake word mode: wait for wake word, then record
        if self._wakeword_mode and self.wakeword:
            self.ui.show_wakeword_waiting()
            self._wake_event.wait()  # Block until wake word detected
            self._wake_event.clear()
            self.ui.show_wake_detected()
            return self._get_voice_input()

        if self._voice_mode:
            return self._get_voice_input()

        # Keyboard mode
        self.ui.show_input_prompt()
        text = self.ui.get_text_input()

        if not text:
            return None

        # "V" or "voice" triggers voice input
        if text.lower() in ("v", "voice"):
            return self._get_voice_input()

        return text

    # ── Response Handling ─────────────────────────────────────

    def _respond(self, text: str):
        """Process user input with intent routing and stage timing."""
        tracer = RequestTracer()
        if hasattr(self.brain, "set_tracer"):
            self.brain.set_tracer(tracer)

        # 1. Intent Classification
        with tracer.trace("intent_routing"):
            intent_result = self.router.classify(text)

        tracer.set_metadata("intent", intent_result.intent.value)
        tracer.set_metadata("subcategory", intent_result.subcategory)

        # 2. Direct COMMAND Execution (<50ms bypass)
        if intent_result.intent == IntentType.COMMAND:
            with tracer.trace("command_execution"):
                handled, result = self.commands.handle(text)

            if handled:
                if result == "__EXIT__":
                    self._running = False
                    tracer.finish()
                    return

                self.ui.show_command_result(result)

                # Speak command results if in voice mode
                if (self._voice_mode or self._wakeword_mode) and self.tts:
                    with tracer.trace("tts"):
                        short = result[:200] if len(result) > 200 else result
                        self._speak_async(short)

                tracer.finish()
                return

        # 3. LLM Reasoning (CHAT or COMPLEX)
        self.ui.show_user_message(text)
        self.ui.show_thinking()

        skip_mem = not intent_result.needs_memory
        skip_code = not intent_result.needs_codebase

        with tracer.trace("llm_reasoning"):
            if self.brain.is_coding_query(text) and config.CODING_MODEL != config.LLM_MODEL:
                self.ui.update_status("Using coding model...")
                try:
                    full_response = self.brain.think_code(text, skip_memory=skip_mem, skip_codebase=skip_code)
                    self.ui.show_son_response(full_response)
                except Exception as e:
                    full_response = self.brain.think(text, skip_memory=skip_mem, skip_codebase=skip_code)
                    self.ui.show_son_response(full_response)
            elif config.LLM_STREAM and not (self.tools and config.TOOL_CALLING_ENABLED):
                token_gen = self.brain.think_stream(text, skip_memory=skip_mem, skip_codebase=skip_code)
                full_response = self.ui.show_son_response_stream(token_gen)
            else:
                full_response = self.brain.think(text, skip_memory=skip_mem, skip_codebase=skip_code)
                self.ui.show_son_response(full_response)

        # 4. Voice response
        if (self._voice_mode or self._wakeword_mode) and self.tts:
            with tracer.trace("tts"):
                self._speak_async(full_response)

        tracer.finish()

    def _speak_async(self, text: str):
        """Speak text in a background thread."""
        # Pause wake word while speaking
        if self.wakeword and self.wakeword.is_listening:
            self.wakeword.pause()

        self.ui.show_speaking()
        thread = threading.Thread(
            target=self.tts.speak_streamed,
            args=(text,),
            daemon=True,
        )
        thread.start()
        thread.join()  # Wait for speech to finish before next input

        # Resume wake word
        if self._wakeword_mode and self.wakeword:
            self.wakeword.resume()

    # ── Main Loop ─────────────────────────────────────────────

    def run(self):
        """Start the SON conversation loop."""
        try:
            self._init_all()
        except Exception as e:
            self.ui.show_error(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return

        self._running = True

        # Start wake word listener if enabled
        if self._wakeword_mode and self.wakeword:
            self.wakeword.start()
            self.ui.update_status("Wake word active — say 'Hey SON' to begin")

        self.ui.divider("Conversation Started")

        # Greet user
        mode_str = "wake word" if self._wakeword_mode else ("voice" if self._voice_mode else "keyboard")
        tool_count = self.tools.count() if self.tools else 0
        greeting = (
            f"Hello Piyush! I'm SON, your personal AI assistant. "
            f"Running in {mode_str} mode with {tool_count} tools available. "
            f"I can control your PC, search the web, analyze your screen, "
            f"manage Docker, and remember everything. How can I help?"
        )
        self.ui.show_son_response(greeting)

        if (self._voice_mode or self._wakeword_mode) and self.tts:
            self._speak_async(greeting)

        # Main conversation loop
        while self._running:
            try:
                user_input = self._get_input()

                if user_input is None:
                    continue

                self._respond(user_input)

            except KeyboardInterrupt:
                self.ui.console.print()
                self._running = False

            except Exception as e:
                self.ui.show_error(str(e))
                import traceback
                traceback.print_exc()

        # Cleanup
        if self.wakeword:
            self.wakeword.stop()

        self.ui.goodbye()


# ── Entry Point ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SON — Personal AI Assistant",
    )
    parser.add_argument(
        "--voice", "-v",
        action="store_true",
        help="Start in voice-first mode (use microphone for input)",
    )
    parser.add_argument(
        "--wakeword", "-w",
        action="store_true",
        help="Start with wake word detection ('Hey SON')",
    )
    parser.add_argument(
        "--scan", "-s",
        action="store_true",
        help="Scan configured codebases on startup",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio devices and exit",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all available tools and exit",
    )

    args = parser.parse_args()

    if args.list_devices:
        AudioManager.list_devices()
        return

    if args.list_tools:
        registry = ToolRegistry()
        from tools.windows_control import register_all as reg_win
        from tools.docker_control import register_all as reg_docker
        from tools.web import register_all as reg_web
        from tools.automation import register_all as reg_auto
        reg_win(registry)
        reg_docker(registry)
        reg_web(registry)
        reg_auto(registry)
        for tool in registry.list_tools():
            print(f"  {tool['name']:<30s} [{tool['category']}] — {tool['description'][:60]}")
        return

    son = Son(
        voice_mode=args.voice,
        scan_on_start=args.scan,
        wakeword_mode=args.wakeword,
    )
    son.run()


if __name__ == "__main__":
    main()
