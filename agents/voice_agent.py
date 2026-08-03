# agents/voice_agent.py — Voice Pipeline (STT, TTS, WakeWord, Barge-in Interrupt) for SON V3
import threading
import queue
import time
import numpy as np
from pathlib import Path

from core.config import Config


class VoiceAgent:
    """
    Manages Speech-to-Text (Whisper), Text-to-Speech (Piper),
    Wake Word Listener ("Hey SON"), and Speech Interruption (Barge-in).
    """

    def __init__(self, state=None, on_speech_detected: callable = None):
        self.state = state
        self._on_speech_detected = on_speech_detected

        self._whisper_model = None
        self._piper_voice = None
        self._wakeword_listener = None

        self._is_speaking = False
        self._speaking_thread = None
        self._stop_speech_flag = threading.Event()

    # ── Speech-to-Text (Faster-Whisper) ────────────────────────

    def _ensure_stt(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                Config.WHISPER_MODEL,
                device=Config.WHISPER_DEVICE,
                compute_type=Config.WHISPER_COMPUTE_TYPE,
            )

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 48000) -> str:
        self._ensure_stt()
        import soundfile as sf
        import tempfile

        tmp_path = Path(tempfile.gettempdir()) / "_son_stt_temp.wav"
        sf.write(str(tmp_path), audio_data, sample_rate)

        segments, info = self._whisper_model.transcribe(
            str(tmp_path),
            beam_size=Config.WHISPER_BEAM_SIZE,
            language=Config.WHISPER_LANGUAGE,
        )

        parts = [seg.text.strip() for seg in segments]
        return " ".join(parts).strip()

    # ── Text-to-Speech (Piper ONNX) ───────────────────────────

    def _ensure_tts(self):
        if self._piper_voice is None:
            try:
                from piper import PiperVoice
                self._piper_voice = PiperVoice.load(
                    Config.PIPER_MODEL_PATH,
                    config_path=Config.PIPER_CONFIG_PATH,
                )
            except Exception:
                self._piper_voice = "cli_fallback"

    def stop_speaking(self):
        """Instantly stop ongoing speech (Barge-in interrupt)."""
        self._stop_speech_flag.set()
        import sounddevice as sd
        sd.stop()
        self._is_speaking = False
        if self.state:
            self.state.is_speaking = False

    def speak(self, text: str, blocking: bool = True):
        """Speak text through speakers with barge-in support."""
        import sounddevice as sd
        import io
        import wave

        self._stop_speech_flag.clear()
        self._is_speaking = True
        if self.state:
            self.state.is_speaking = True

        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        self._ensure_tts()

        for sentence in sentences:
            if self._stop_speech_flag.is_set():
                break

            try:
                audio_buffer = io.BytesIO()
                with wave.open(audio_buffer, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(Config.TTS_SAMPLE_RATE)
                    self._piper_voice.synthesize(sentence, wav_file)

                audio_buffer.seek(0)
                with wave.open(audio_buffer, "rb") as wav_file:
                    raw = wav_file.readframes(wav_file.getnframes())
                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                sd.play(audio, samplerate=Config.TTS_SAMPLE_RATE)
                while sd.get_stream().active:
                    if self._stop_speech_flag.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)

            except Exception:
                pass

        self._is_speaking = False
        if self.state:
            self.state.is_speaking = False

    # ── Wake Word & VAD ───────────────────────────────────────

    def record_vad(self) -> np.ndarray | None:
        """Record microphone audio using Voice Activity Detection."""
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

                rms = float(np.sqrt(np.mean(chunk**2)))
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

        if self.state:
            self.state.is_listening = False

        if not speech_detected or not chunks:
            return None

        audio = np.concatenate(chunks).flatten()
        return audio if (len(audio) / Config.SAMPLE_RATE) >= Config.VAD_MIN_SPEECH_DURATION else None
