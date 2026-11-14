# agents/voice_agent.py — Voice Pipeline (STT, TTS, WakeWord, Barge-in Interrupt) for SON V3
import threading
import queue
import time
import numpy as np
import logging
from core.config import Config
from stt import SpeechToText
from tts import TextToSpeech
from native.son_native import fast_rms

logger = Config.get_logger(__name__)


class VoiceAgent:
    """
    Manages Speech-to-Text (Whisper), Text-to-Speech (Piper),
    Wake Word Listener ("Hey SON"), and Speech Interruption (Barge-in).
    Delegates to optimized STT and TTS engines.
    """

    def __init__(self, state=None, on_speech_detected: callable = None, audio_manager=None):
        self.state = state
        self._on_speech_detected = on_speech_detected
        self._audio = audio_manager

        self._stt = SpeechToText()
        self._tts = TextToSpeech()

        self._is_speaking = False
        self._stop_speech_flag = threading.Event()

    # ── Speech-to-Text ────────────────────────────────────────

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 48000) -> str:
        """Transcribe audio array using optimized SpeechToText engine."""
        return self._stt.transcribe(audio_data, sample_rate=sample_rate)

    # ── Text-to-Speech ────────────────────────────────────────

    def stop_speaking(self):
        """Instantly stop ongoing speech (Barge-in interrupt)."""
        self._stop_speech_flag.set()
        self._tts.stop()
        self._is_speaking = False
        if self.state:
            self.state.is_speaking = False

    def speak(self, text: str, blocking: bool = True):
        """Speak text through speakers with barge-in support."""
        self._stop_speech_flag.clear()
        self._is_speaking = True
        if self.state:
            self.state.is_speaking = True

        try:
            self._tts.speak_streamed(text)
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}", exc_info=True)
        finally:
            self._is_speaking = False
            if self.state:
                self.state.is_speaking = False

    # ── Wake Word & VAD ───────────────────────────────────────

    def record_vad(self) -> np.ndarray | None:
        """Record microphone audio using fast Voice Activity Detection."""
        if self._audio is None:
            from audio import AudioManager
            self._audio = AudioManager()

        if self.state:
            self.state.is_listening = True

        try:
            return self._audio.record_vad()
        finally:
            if self.state:
                self.state.is_listening = False
