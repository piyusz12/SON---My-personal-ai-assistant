# tts.py — Text-to-Speech Engine (Piper ONNX)
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
    Generates speech audio from text and plays it through speakers.
    """

    def __init__(self):
        self._model_path = config.PIPER_MODEL_PATH
        self._config_path = config.PIPER_CONFIG_PATH
        self._sample_rate = config.TTS_SAMPLE_RATE
        self._synthesizer = None  # lazy load
        self._playback_queue = queue.Queue()
        self._is_speaking = False

    def _ensure_model(self):
        """Lazy-load the Piper model on first use."""
        if self._synthesizer is None:
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
        Split text into sentences and stream TTS for lower latency.
        Starts speaking the first sentence while synthesizing the rest.
        """
        import sounddevice as sd

        # Simple sentence splitting
        sentences = self._split_sentences(text)
        if not sentences:
            return

        self._is_speaking = True

        for sentence in sentences:
            if not self._is_speaking:
                break

            audio = self.synthesize(sentence)
            sd.play(audio, samplerate=self._sample_rate)
            sd.wait()

        self._is_speaking = False

    def stop(self):
        """Stop ongoing speech playback."""
        import sounddevice as sd
        self._is_speaking = False
        sd.stop()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences for streamed TTS."""
        import re
        # Split on sentence-ending punctuation, keeping the punctuation
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p.strip() for p in parts if p.strip()]
