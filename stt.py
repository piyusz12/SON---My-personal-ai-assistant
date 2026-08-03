# stt.py — Speech-to-Text Engine (Faster-Whisper)
import numpy as np
from pathlib import Path

import config


class SpeechToText:
    """Wraps Faster-Whisper for local GPU-accelerated speech recognition."""

    def __init__(self):
        self._model = None  # lazy load — heavy model
        self._model_name = config.WHISPER_MODEL
        self._device = config.WHISPER_DEVICE
        self._compute_type = config.WHISPER_COMPUTE_TYPE
        self._beam_size = config.WHISPER_BEAM_SIZE
        self._language = config.WHISPER_LANGUAGE

    def _ensure_model(self):
        """Lazy-load the Whisper model on first use."""
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

        Args:
            audio: Either a numpy array of audio samples or a path to a .wav file.
            sample_rate: Sample rate (required if audio is numpy array).

        Returns:
            Transcribed text string.
        """
        self._ensure_model()

        if isinstance(audio, (str, Path)):
            # File path
            source = str(audio)
        elif isinstance(audio, np.ndarray):
            # Numpy array — write to temp file
            import soundfile as sf
            import tempfile
            tmp = Path(tempfile.gettempdir()) / "_son_stt_tmp.wav"
            sr = sample_rate or config.SAMPLE_RATE
            sf.write(str(tmp), audio, sr)
            source = str(tmp)
        else:
            raise TypeError(f"Expected numpy array or file path, got {type(audio)}")

        segments, info = self._model.transcribe(
            source,
            beam_size=self._beam_size,
            language=self._language,
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        return " ".join(text_parts)

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
            import soundfile as sf
            import tempfile
            tmp = Path(tempfile.gettempdir()) / "_son_stt_tmp.wav"
            sr = sample_rate or config.SAMPLE_RATE
            sf.write(str(tmp), audio, sr)
            source = str(tmp)
        else:
            raise TypeError(f"Expected numpy array or file path, got {type(audio)}")

        segments, info = self._model.transcribe(
            source,
            beam_size=self._beam_size,
            language=self._language,
        )

        result = []
        for seg in segments:
            result.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })

        return result
