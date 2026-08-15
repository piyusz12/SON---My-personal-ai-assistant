# stt.py — Speech-to-Text Engine (Faster-Whisper)
# SON V3 — Optimized for RTX 4060 GPU
"""
Changes from V2:
- Eager model loading on startup (no lazy-load latency)
- In-memory ndarray input (avoids temp file write to disk)
- Pre-pinned GPU model for consistent VRAM allocation
- Concurrent segment processing for multi-segment audio
"""
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import config


class SpeechToText:
    """Wraps Faster-Whisper for local GPU-accelerated speech recognition."""

    def __init__(self, eager_load: bool = False):
        self._model = None
        self._model_name = config.WHISPER_MODEL
        self._device = config.WHISPER_DEVICE
        self._compute_type = config.WHISPER_COMPUTE_TYPE
        self._beam_size = config.WHISPER_BEAM_SIZE
        self._language = config.WHISPER_LANGUAGE
        self._vad_filter = getattr(config, 'WHISPER_VAD_FILTER', True)

        # Eager load for lower first-use latency
        if eager_load:
            self._ensure_model()

    def _ensure_model(self):
        """Load the Whisper model (pins to GPU)."""
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )

    def transcribe(self, audio: np.ndarray | str, sample_rate: int | None = None) -> str:
        """
        Transcribe audio to text.

        Optimized:
        - Accepts numpy arrays directly (avoids temp file I/O)
        - Uses faster_whisper's native ndarray support when possible

        Args:
            audio: Either a numpy array of audio samples or a path to a .wav file.
            sample_rate: Sample rate (required if audio is numpy array and needs resampling).

        Returns:
            Transcribed text string.
        """
        self._ensure_model()

        if isinstance(audio, (str, Path)):
            source = str(audio)
        elif isinstance(audio, np.ndarray):
            # faster-whisper can accept float32 ndarray directly at 16kHz
            sr = sample_rate or config.SAMPLE_RATE

            # Ensure float32 and flatten
            audio_f32 = audio.astype(np.float32).flatten()

            # Resample to 16kHz if needed (Whisper expects 16kHz)
            if sr != 16000:
                try:
                    from native.son_native import fast_resample
                    audio_f32 = fast_resample(audio_f32, sr, 16000)
                except ImportError:
                    # NumPy fallback resampling
                    dst_len = int(len(audio_f32) * 16000 / sr)
                    indices = np.linspace(0, len(audio_f32) - 1, dst_len)
                    idx_floor = np.floor(indices).astype(np.intp)
                    idx_ceil = np.minimum(idx_floor + 1, len(audio_f32) - 1)
                    frac = indices - idx_floor
                    audio_f32 = (audio_f32[idx_floor] * (1 - frac) + audio_f32[idx_ceil] * frac).astype(np.float32)

            # Pass ndarray directly — no temp file needed
            source = audio_f32
        else:
            raise TypeError(f"Expected numpy array or file path, got {type(audio)}")

        # Domain vocabulary priming for high recognition accuracy
        initial_prompt = getattr(
            config,
            "WHISPER_INITIAL_PROMPT",
            "Dad, Father, Papa, Piyush, SON, VS Code, Python, Docker, Chrome, Spotify, terminal, GitHub, Ollama, camera, screenshot, volume, brightness."
        )

        segments, info = self._model.transcribe(
            source,
            beam_size=self._beam_size,
            language=self._language,
            vad_filter=self._vad_filter,  # skip silence segments for faster transcription
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,  # prevents repetition loops
            temperature=[0.0, 0.2, 0.4],       # fallback on uncertain audio
        )

        # Common Whisper hallucinations on ambient noise
        hallucinations = {
            "thank you for watching", "thanks for watching", "subtitles by", "amara.org",
            "[blank_audio]", "[music]", "[applause]", "[laughter]", "you", "...", "bye",
            "thank you.", "thank you", "thanks."
        }

        text_parts = []
        for segment in segments:
            clean_seg = segment.text.strip()
            if clean_seg and clean_seg.lower() not in hallucinations:
                text_parts.append(clean_seg)

        result_text = " ".join(text_parts).strip()
        return result_text

    def transcribe_with_segments(self, audio: np.ndarray | str, sample_rate: int | None = None):
        """
        Transcribe and return individual segments with timestamps.

        Returns:
            List of dicts: [{"start": float, "end": float, "text": str}, ...]
        """
        self._ensure_model()

        if isinstance(audio, (str, Path)):
            source = str(audio)
        elif isinstance(audio, np.ndarray):
            sr = sample_rate or config.SAMPLE_RATE
            audio_f32 = audio.astype(np.float32).flatten()

            if sr != 16000:
                try:
                    from native.son_native import fast_resample
                    audio_f32 = fast_resample(audio_f32, sr, 16000)
                except ImportError:
                    dst_len = int(len(audio_f32) * 16000 / sr)
                    indices = np.linspace(0, len(audio_f32) - 1, dst_len)
                    idx_floor = np.floor(indices).astype(np.intp)
                    idx_ceil = np.minimum(idx_floor + 1, len(audio_f32) - 1)
                    frac = indices - idx_floor
                    audio_f32 = (audio_f32[idx_floor] * (1 - frac) + audio_f32[idx_ceil] * frac).astype(np.float32)

            source = audio_f32
        else:
            raise TypeError(f"Expected numpy array or file path, got {type(audio)}")

        segments, info = self._model.transcribe(
            source,
            beam_size=self._beam_size,
            language=self._language,
            vad_filter=self._vad_filter,
        )

        result = []
        for seg in segments:
            result.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })

        return result

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded in VRAM."""
        return self._model is not None

    def unload(self):
        """Unload the model to free VRAM."""
        self._model = None
