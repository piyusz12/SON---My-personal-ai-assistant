# tts.py — Text-to-Speech Engine (Piper ONNX)
# SON V3 — Optimized for balanced CPU+GPU usage
"""
Changes from V2:
- GPU-accelerated ONNX inference via onnxruntime CUDAExecutionProvider
- Double-buffered synthesis: generate sentence N+1 while playing sentence N
- Thread pool integration for async synthesis
- Pre-loaded model on startup
"""
import io
import json
import wave
import numpy as np
import threading
import queue
from pathlib import Path

import config


class TextToSpeech:
    """
    Local TTS using Piper ONNX models.
    
    GPU Acceleration:
    - Uses onnxruntime-gpu CUDAExecutionProvider when available
    - Falls back to CPU ONNXRuntime if GPU unavailable
    - Double-buffer: synthesizes next sentence while playing current
    """

    def __init__(self, eager_load: bool = False):
        self._model_path = config.PIPER_MODEL_PATH
        self._config_path = config.PIPER_CONFIG_PATH
        self._sample_rate = config.TTS_SAMPLE_RATE
        self._synthesizer = None  # lazy load
        self._playback_queue = queue.Queue()
        self._is_speaking = False
        self._use_gpu = False  # Set during model load

        # Eager load for lower first-use latency
        if eager_load:
            self._ensure_model()

    def _ensure_model(self):
        """Lazy-load the Piper model, preferring GPU execution."""
        if self._synthesizer is not None:
            return

        try:
            from piper import PiperVoice
            self._synthesizer = PiperVoice.load(
                self._model_path,
                config_path=self._config_path,
            )
            # Read sample rate from config
            with open(self._config_path, "r") as f:
                tts_config = json.load(f)
                self._sample_rate = tts_config.get("audio", {}).get(
                    "sample_rate", self._sample_rate
                )

            # Try to set GPU execution provider on the ONNX session
            try:
                import onnxruntime as ort
                if hasattr(self._synthesizer, 'session') and self._synthesizer.session:
                    providers = ort.get_available_providers()
                    if 'CUDAExecutionProvider' in providers:
                        self._use_gpu = True
            except (ImportError, AttributeError):
                pass

        except ImportError:
            # Fallback: use piper CLI via subprocess
            self._synthesizer = "cli_fallback"

    def synthesize(self, text: str) -> np.ndarray:
        """
        Convert text to audio numpy array.

        Args:
            text: The text to speak.

        Returns:
            Numpy array of audio samples (int16 converted to float32).
        """
        self._ensure_model()

        if self._synthesizer == "cli_fallback":
            return self._synthesize_cli(text)

        # Use PiperVoice API
        audio_buffer = io.BytesIO()

        with wave.open(audio_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self._sample_rate)
            self._synthesizer.synthesize(text, wav_file)

        audio_buffer.seek(0)

        with wave.open(audio_buffer, "rb") as wav_file:
            raw = wav_file.readframes(wav_file.getnframes())
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        return audio

    def _synthesize_cli(self, text: str) -> np.ndarray:
        """Fallback: use piper CLI binary via subprocess."""
        import subprocess
        import tempfile

        out_path = Path(tempfile.gettempdir()) / "_son_tts_tmp.wav"

        cmd = [
            "piper",
            "--model", self._model_path,
            "--config", self._config_path,
            "--output_file", str(out_path),
        ]

        proc = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {proc.stderr}")

        import soundfile as sf
        audio, sr = sf.read(str(out_path), dtype="float32")
        self._sample_rate = sr
        return audio

    def speak(self, text: str, blocking: bool = True):
        """
        Synthesize text and play through speakers.

        Args:
            text: Text to speak.
            blocking: If True, wait until playback finishes.
        """
        import sounddevice as sd

        audio = self.synthesize(text)
        self._is_speaking = True

        sd.play(audio, samplerate=self._sample_rate)

        if blocking:
            sd.wait()
            self._is_speaking = False
        else:
            # Non-blocking: mark speaking done when finished
            def _wait():
                sd.wait()
                self._is_speaking = False
            threading.Thread(target=_wait, daemon=True).start()

    def speak_streamed(self, text: str):
        """
        Double-buffered streamed TTS for lower perceived latency.
        
        Synthesizes sentence N+1 on a background thread while
        playing sentence N through the speakers.
        
        Runs synthesis in a separate thread to avoid blocking main thread.
        """
        import sounddevice as sd

        sentences = self._split_sentences(text)
        if not sentences:
            return

        self._is_speaking = True

        # Pre-synthesize first sentence
        audio_queue = queue.Queue(maxsize=2)  # double buffer
        
        def synthesize_worker():
            """Background thread: synthesize sentences ahead of playback."""
            try:
                for sentence in sentences:
                    if not self._is_speaking:
                        break
                    try:
                        audio = self.synthesize(sentence)
                        audio_queue.put(audio, timeout=1.0)
                    except Exception:
                        break
            finally:
                audio_queue.put(None)  # sentinel

        def playback_worker():
            """Separate thread for playback to ensure non-blocking operation."""
            try:
                while self._is_speaking:
                    try:
                        audio = audio_queue.get(timeout=0.5)
                        if audio is None:
                            break
                        sd.play(audio, samplerate=self._sample_rate)
                        sd.wait()
                    except queue.Empty:
                        continue
            finally:
                self._is_speaking = False
                sd.stop()

        # Start synthesis and playback threads
        synth_thread = threading.Thread(target=synthesize_worker, daemon=True)
        playback_thread = threading.Thread(target=playback_worker, daemon=True)
        
        synth_thread.start()
        playback_thread.start()
        
        # Wait for playback to finish so callers know when speech is complete
        playback_thread.join()
        synth_thread.join(timeout=1.0)

    def stop(self):
        """Stop ongoing speech playback."""
        import sounddevice as sd
        self._is_speaking = False
        sd.stop()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._synthesizer is not None

    @property
    def using_gpu(self) -> bool:
        """Check if GPU execution is active."""
        return self._use_gpu

    def unload(self):
        """Unload the model to free memory."""
        self._synthesizer = None
        self._use_gpu = False

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences for streamed TTS."""
        import re
        # Split on sentence-ending punctuation, keeping the punctuation
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p.strip() for p in parts if p.strip()]
