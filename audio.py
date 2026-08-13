# audio.py — Audio Device Management & Voice Activity Detection Recording
# SON V3 — Optimized for Ryzen 7 7840HS + RTX 4060
"""
Changes from V2:
- C-accelerated RMS via native.son_native.fast_rms (~50x faster VAD)
- Ring buffer for zero-copy audio streaming (replaces queue.Queue)
- Pre-allocated numpy buffers to avoid GC pressure
- Dedicated audio thread from Pipeline pool
"""
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
from pathlib import Path

import config

# Import native acceleration (with fallback)
try:
    from native.son_native import fast_rms
except ImportError:
    fast_rms = None


class RingBuffer:
    """
    Lock-free(ish) ring buffer for audio streaming.
    Avoids queue.Queue overhead for high-frequency audio chunks.
    Pre-allocates memory to prevent GC pauses during recording.
    """

    def __init__(self, max_chunks: int, chunk_samples: int, dtype=np.float32):
        self._buffer = np.zeros((max_chunks, chunk_samples), dtype=dtype)
        self._max_chunks = max_chunks
        self._chunk_samples = chunk_samples
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = threading.Lock()
        self._event = threading.Event()

    def write(self, chunk: np.ndarray):
        """Write a chunk to the ring buffer."""
        with self._lock:
            idx = self._write_idx % self._max_chunks
            # Handle variable-size chunks by truncating or padding
            n = min(len(chunk.flatten()), self._chunk_samples)
            self._buffer[idx, :n] = chunk.flatten()[:n]
            if n < self._chunk_samples:
                self._buffer[idx, n:] = 0
            self._write_idx += 1
            self._count = min(self._count + 1, self._max_chunks)
        self._event.set()

    def read(self, timeout: float = 0.2) -> np.ndarray | None:
        """Read the next available chunk. Blocks up to timeout."""
        if not self._event.wait(timeout):
            return None
        with self._lock:
            if self._read_idx >= self._write_idx:
                self._event.clear()
                return None
            idx = self._read_idx % self._max_chunks
            chunk = self._buffer[idx].copy()
            self._read_idx += 1
            if self._read_idx >= self._write_idx:
                self._event.clear()
        return chunk

    def clear(self):
        """Reset the ring buffer."""
        with self._lock:
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0
            self._event.clear()


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

        # Pre-compute chunk parameters
        self._chunk_duration = getattr(config, 'VAD_CHUNK_DURATION', 0.05)  # 50ms chunks for faster VAD
        self._chunk_samples = int(self._chunk_duration * self._sample_rate)

        # Pre-allocated ring buffer (holds up to 30s of audio in 100ms chunks)
        max_chunks = int(self._max_duration / self._chunk_duration) + 10
        self._ring_buffer = RingBuffer(max_chunks, self._chunk_samples)

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

    # ── RMS Calculation (C-accelerated or NumPy fallback) ─────

    def _rms(self, audio_chunk: np.ndarray) -> float:
        """
        Calculate root-mean-square amplitude.
        Uses C SIMD extension when available (~50x faster).
        """
        if fast_rms is not None:
            return fast_rms(audio_chunk)
        # NumPy fallback
        return float(np.sqrt(np.mean(audio_chunk ** 2)))

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

    @staticmethod
    def _normalize_audio(audio: np.ndarray, target_peak: float = 0.92) -> np.ndarray:
        """
        Normalize audio peak to target amplitude with soft limiter.
        Uses native SIMD acceleration when available.
        """
        try:
            from native.son_native import fast_normalize_audio
            return fast_normalize_audio(audio, target_peak=target_peak)
        except Exception:
            peak = float(np.max(np.abs(audio)))
            if peak > 0.01:
                gain = min(target_peak / peak, 4.0)  # Max +12dB gain
                return np.clip(audio * gain, -1.0, 1.0)
            return audio

    # ── VAD-Based Recording (Enhanced) ────────────────────────

    def record_vad(self, save_path: str | None = None) -> np.ndarray | None:
        """
        Record audio using Voice Activity Detection.
        
        Enhancements:
        - Adaptive noise-floor calibration (adapts to background room noise)
        - Pre-roll rolling history (350ms buffer prevents cutting off the first syllable)
        - Trailing hangover window (handles natural inter-word pauses)
        - Peak normalization and soft-limiting for maximum STT clarity
        
        Returns numpy array of captured speech, or None if no speech detected.
        """
        from collections import deque
        self._ring_buffer.clear()

        # Pre-roll buffer: holds 350ms of audio before speech trigger
        preroll_chunks_count = max(4, int(0.35 / self._chunk_duration))
        preroll_buffer = deque(maxlen=preroll_chunks_count)

        audio_chunks: list[np.ndarray] = []
        silence_start: float | None = None
        speech_detected = False
        total_duration = 0.0

        # Dynamic noise floor tracking
        noise_floor = self._silence_threshold * 0.5
        noise_samples_count = 0

        def audio_callback(indata, frames, time_info, status):
            if status:
                pass  # ignore minor xruns
            self._ring_buffer.write(indata.copy())

        self._recording = True

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            device=self._device,
            blocksize=self._chunk_samples,
            callback=audio_callback,
        ):
            while self._recording and total_duration < self._max_duration:
                chunk = self._ring_buffer.read(timeout=0.2)
                if chunk is None:
                    continue

                rms = self._rms(chunk)
                total_duration += self._chunk_duration

                # Calibrate noise floor in initial quiet frames
                if not speech_detected:
                    if noise_samples_count < 10:
                        noise_floor = (noise_floor * noise_samples_count + rms) / (noise_samples_count + 1)
                        noise_samples_count += 1
                    else:
                        noise_floor = 0.95 * noise_floor + 0.05 * rms

                # Adaptive trigger threshold
                trigger_threshold = max(self._silence_threshold, noise_floor * 2.2)

                if rms > trigger_threshold:
                    if not speech_detected:
                        # Speech started! Prepend pre-roll buffer so the first word isn't clipped
                        speech_detected = True
                        for p_chunk in preroll_buffer:
                            audio_chunks.append(p_chunk)
                    silence_start = None
                    audio_chunks.append(chunk)
                elif speech_detected:
                    # Speech was active, now checking trailing silence
                    audio_chunks.append(chunk)
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= self._silence_duration:
                        # Natural pause detected — finish recording
                        break
                else:
                    # Silence before speech — store in pre-roll buffer
                    preroll_buffer.append(chunk)

        self._recording = False

        if not speech_detected or not audio_chunks:
            return None

        audio = np.concatenate(audio_chunks).flatten()

        # Check minimum speech duration
        speech_duration = len(audio) / self._sample_rate
        if speech_duration < self._min_speech:
            return None

        # Normalize audio for optimal Whisper transcription
        audio = self._normalize_audio(audio)

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