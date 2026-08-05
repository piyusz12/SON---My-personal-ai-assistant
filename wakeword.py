# wakeword.py — "Hey SON" Wake Word Detection (OpenWakeWord)
# SON V3 — Optimized for Ryzen 7 7840HS
"""
Continuously listens for the wake word in a background thread.
When detected, triggers a callback to begin voice input.

Uses openwakeword — a lightweight, fully offline wake word engine.
Pre-trained models: "hey_jarvis", "hey_mycroft", "alexa", etc.

Changes from V2:
- C-accelerated 48kHz→16kHz resampling via fast_resample
- Pre-allocated numpy buffers to avoid GC during real-time audio
- Reduced allocation overhead with persistent int16 buffer
"""
import threading
import time
import numpy as np

import config

# Import native acceleration (with fallback)
try:
    from native.son_native import fast_resample
    _HAS_NATIVE_RESAMPLE = True
except ImportError:
    _HAS_NATIVE_RESAMPLE = False


class WakeWordListener:
    """
    Background wake word detector using openwakeword.
    Listens on the microphone and fires a callback when the wake word is heard.
    """

    def __init__(self, on_wake: callable = None):
        """
        Args:
            on_wake: Callback function invoked when wake word is detected.
                     Called with no arguments.
        """
        self._on_wake = on_wake
        self._model_name = config.WAKEWORD_MODEL
        self._threshold = config.WAKEWORD_THRESHOLD
        self._sample_rate = config.WAKEWORD_SAMPLE_RATE
        self._chunk_size = config.WAKEWORD_CHUNK_SIZE
        self._running = False
        self._thread: threading.Thread | None = None
        self._oww_model = None

        # Pre-allocate reusable buffer for int16 conversion
        # (avoids allocation on every audio callback)
        self._int16_buffer = np.zeros(self._chunk_size, dtype=np.int16)

    # ── Model Loading ─────────────────────────────────────────

    def _ensure_model(self):
        """Lazy-load the openwakeword model."""
        if self._oww_model is None:
            try:
                from openwakeword.model import Model as OWWModel
                self._oww_model = OWWModel(
                    wakeword_models=[self._model_name],
                    inference_framework="onnx",
                )
            except ImportError:
                raise ImportError(
                    "openwakeword is not installed. "
                    "Install it with: pip install openwakeword"
                )
            except Exception as e:
                # If the model name isn't found, try loading without specifying
                from openwakeword.model import Model as OWWModel
                self._oww_model = OWWModel(inference_framework="onnx")

    # ── Listening Loop ────────────────────────────────────────

    def _listen_loop(self):
        """Main listening loop — runs in a background thread."""
        import sounddevice as sd

        self._ensure_model()

        # Check if mic is running at a different rate than OWW expects
        mic_rate = config.SAMPLE_RATE  # 48000
        oww_rate = self._sample_rate    # 16000
        needs_resample = (mic_rate != oww_rate)

        # Calculate mic blocksize to produce oww_chunk_size samples after resample
        if needs_resample:
            mic_blocksize = int(self._chunk_size * mic_rate / oww_rate)
        else:
            mic_blocksize = self._chunk_size

        def audio_callback(indata, frames, time_info, status):
            if not self._running:
                raise sd.CallbackAbort()

            audio_float = indata.flatten()

            # Resample if needed (48kHz → 16kHz)
            if needs_resample:
                if _HAS_NATIVE_RESAMPLE:
                    # C-accelerated resampling (~10x faster)
                    audio_float = fast_resample(audio_float, mic_rate, oww_rate)
                else:
                    # NumPy fallback
                    ratio = oww_rate / mic_rate
                    dst_len = int(len(audio_float) * ratio)
                    indices = np.linspace(0, len(audio_float) - 1, dst_len)
                    idx_floor = np.floor(indices).astype(np.intp)
                    idx_ceil = np.minimum(idx_floor + 1, len(audio_float) - 1)
                    frac = (indices - idx_floor).astype(np.float32)
                    audio_float = audio_float[idx_floor] * (1 - frac) + audio_float[idx_ceil] * frac

            # Convert to int16 as openwakeword expects
            # Re-use pre-allocated buffer when possible
            n = min(len(audio_float), len(self._int16_buffer))
            np.multiply(audio_float[:n], 32767, out=self._int16_buffer[:n].astype(np.float32, copy=False))
            audio_int16 = (audio_float[:n] * 32767).astype(np.int16)

            # Feed to openwakeword
            prediction = self._oww_model.predict(audio_int16)

            # Check all model scores
            for model_name, score in prediction.items():
                if score >= self._threshold:
                    # Wake word detected!
                    self._oww_model.reset()  # Reset to avoid re-triggering

                    if self._on_wake:
                        # Fire callback in a separate thread to not block audio
                        threading.Thread(
                            target=self._on_wake,
                            daemon=True,
                        ).start()

        try:
            with sd.InputStream(
                samplerate=mic_rate if needs_resample else self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=mic_blocksize,
                device=config.MIC_DEVICE,
                callback=audio_callback,
            ):
                while self._running:
                    time.sleep(0.1)
        except sd.CallbackAbort:
            pass
        except Exception as e:
            print(f"[WakeWord] Error: {e}")

    # ── Control ───────────────────────────────────────────────

    def start(self):
        """Start listening for wake word in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWordListener",
        )
        self._thread.start()

    def stop(self):
        """Stop the wake word listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_listening(self) -> bool:
        return self._running

    def pause(self):
        """Temporarily pause detection (e.g. while SON is speaking)."""
        self._running = False

    def resume(self):
        """Resume detection after pause."""
        if not self._running:
            self.start()
