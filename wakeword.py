# wakeword.py — "Hey SON" Wake Word Detection (OpenWakeWord)
"""
Continuously listens for the wake word in a background thread.
When detected, triggers a callback to begin voice input.

Uses openwakeword — a lightweight, fully offline wake word engine.
Pre-trained models: "hey_jarvis", "hey_mycroft", "alexa", etc.
"""
import threading
import time
import numpy as np

import config


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

        def audio_callback(indata, frames, time_info, status):
            if not self._running:
                raise sd.CallbackAbort()

            # Convert to int16 as openwakeword expects
            audio_int16 = (indata.flatten() * 32767).astype(np.int16)

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
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self._chunk_size,
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
