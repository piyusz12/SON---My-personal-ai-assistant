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

    def __init__(self, state=None, on_speech_detected: callable = None):
        self.state = state
        self._on_speech_detected = on_speech_detected

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
        import sounddevice as sd

        chunk_samples = int(0.1 * Config.SAMPLE_RATE)
        chunks = []
        silence_start = None
        speech_detected = False
        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(indata.copy())

        if self.state:
            self.state.is_listening = True

        try:
            with sd.InputStream(
                samplerate=Config.SAMPLE_RATE,
                channels=Config.CHANNELS,
                dtype=Config.AUDIO_DTYPE,
                blocksize=chunk_samples,
                callback=callback,
            ):
                start_t = time.time()
                while time.time() - start_t < Config.VAD_MAX_RECORD_DURATION:
                    try:
                        chunk = audio_q.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    # C-accelerated or BLAS-accelerated RMS computation
                    rms = fast_rms(chunk)
                    if rms > Config.VAD_SILENCE_THRESHOLD:
                        if self._is_speaking:
                            self.stop_speaking()  # Barge-in: User spoke while SON was talking
                        speech_detected = True
                        silence_start = None
                        chunks.append(chunk)
                    elif speech_detected:
                        chunks.append(chunk)
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= Config.VAD_SILENCE_DURATION:
                            break
        finally:
            if self.state:
                self.state.is_listening = False

        if not speech_detected or not chunks:
            return None

        audio = np.concatenate(chunks).flatten()
        return audio if (len(audio) / Config.SAMPLE_RATE) >= Config.VAD_MIN_SPEECH_DURATION else None
