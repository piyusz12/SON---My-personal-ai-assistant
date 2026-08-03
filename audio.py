# audio.py — Audio Device Management & Voice Activity Detection Recording
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
from pathlib import Path

import config


class AudioManager:
    """Manages microphone input, speaker output, and VAD-based recording."""

    def __init__(self):
        self._device = config.MIC_DEVICE
        self._sample_rate = config.SAMPLE_RATE
        self._channels = config.CHANNELS
        self._dtype = config.AUDIO_DTYPE

        # VAD parameters
        self._silence_threshold = config.VAD_SILENCE_THRESHOLD
        self._silence_duration = config.VAD_SILENCE_DURATION
        self._min_speech = config.VAD_MIN_SPEECH_DURATION
        self._max_duration = config.VAD_MAX_RECORD_DURATION

        # State
        self._recording = False
        self._audio_queue = queue.Queue()

    # ── Device Discovery ──────────────────────────────────────

    @staticmethod
    def list_devices():
        """Print all audio devices with their capabilities."""
        devices = sd.query_devices()
        print("\n╔══════════════════════════════════════════════╗")
        print("║            AUDIO DEVICES                     ║")
        print("╚══════════════════════════════════════════════╝\n")
        for i, dev in enumerate(devices):
            marker = ""
            if i == sd.default.device[0]:
                marker += " ◄ MIC"
            if i == sd.default.device[1]:
                marker += " ◄ SPK"
            print(
                f"  {i:2d} │ {dev['name']:<40s} │ "
                f"In:{dev['max_input_channels']} Out:{dev['max_output_channels']}"
                f"{marker}"
            )
        print()

    @staticmethod
    def get_default_input():
        return sd.default.device[0]

    @staticmethod
    def get_default_output():
        return sd.default.device[1]

    # ── Fixed-Duration Recording ──────────────────────────────

    def record_fixed(self, duration: float = 5.0, save_path: str | None = None) -> np.ndarray:
        """Record for a fixed duration. Returns numpy array of audio."""
        frames = int(duration * self._sample_rate)
        audio = sd.rec(
            frames,
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            device=self._device,
        )
        sd.wait()

        if save_path:
            sf.write(save_path, audio, self._sample_rate)

        return audio.flatten()

    # ── VAD-Based Recording ───────────────────────────────────

    def _rms(self, audio_chunk: np.ndarray) -> float:
        """Calculate root-mean-square amplitude."""
        return float(np.sqrt(np.mean(audio_chunk ** 2)))

    def record_vad(self, save_path: str | None = None) -> np.ndarray | None:
        """
        Record audio using Voice Activity Detection.
        Starts capturing when speech is detected, stops after sustained silence.
        Returns numpy array of captured speech, or None if no speech detected.
        """
        chunk_duration = 0.1  # 100ms chunks
        chunk_samples = int(chunk_duration * self._sample_rate)

        audio_chunks: list[np.ndarray] = []
        silence_start: float | None = None
        speech_detected = False
        total_duration = 0.0

        def audio_callback(indata, frames, time_info, status):
            if status:
                pass  # ignore minor xruns
            self._audio_queue.put(indata.copy())

        self._recording = True

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            device=self._device,
            blocksize=chunk_samples,
            callback=audio_callback,
        ):
            while self._recording and total_duration < self._max_duration:
                try:
                    chunk = self._audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                rms = self._rms(chunk)
                total_duration += chunk_duration

                if rms > self._silence_threshold:
                    # Speech detected
                    speech_detected = True
                    silence_start = None
                    audio_chunks.append(chunk)
                elif speech_detected:
                    # We had speech, now silence
                    audio_chunks.append(chunk)  # keep trailing silence
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self._silence_duration:
                        # Enough silence — stop
                        break

        self._recording = False

        if not speech_detected or not audio_chunks:
            return None

        audio = np.concatenate(audio_chunks).flatten()

        # Check minimum speech duration
        speech_duration = len(audio) / self._sample_rate
        if speech_duration < self._min_speech:
            return None

        if save_path:
            sf.write(save_path, audio, self._sample_rate)

        return audio

    def stop_recording(self):
        """Signal the recording loop to stop."""
        self._recording = False

    # ── Playback ──────────────────────────────────────────────

    def play(self, audio: np.ndarray, sample_rate: int | None = None, blocking: bool = True):
        """Play audio through the default output device."""
        sr = sample_rate or self._sample_rate
        sd.play(audio, samplerate=sr)
        if blocking:
            sd.wait()

    def stop_playback(self):
        """Stop any ongoing playback."""
        sd.stop()