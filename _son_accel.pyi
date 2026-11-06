"""
Type stub file for the _son_accel native C extension.
Accelerated functions compiled into _son_accel (.pyd / .so).
"""
from typing import Any

def fast_rms(buffer: Any) -> float:
    """Compute RMS amplitude of float32 audio buffer using AVX2 SIMD."""
    ...

def fast_resample(buffer: Any, src_rate: int, dst_rate: int) -> bytes:
    """Resample float32 audio from src_rate to dst_rate using linear interpolation."""
    ...

def fast_chunk_text(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    """Split text into overlapping line-based chunks for embedding."""
    ...

def fast_sha256_hex(data: str) -> str:
    """Compute SHA-256 of string data, return first 16 hex chars."""
    ...

def fast_audio_energy(buffer: Any, chunk_samples: int) -> list[float]:
    """Compute per-chunk RMS energy levels across audio buffer."""
    ...

def fast_classify_intent(text: str) -> tuple[int, str] | None:
    """C-accelerated lightning-fast intent routing bypassing Python regex.
    Returns (intent_id, subcategory) or None.
    intent_id: 1 for COMMAND, 2 for CHAT.
    """
    ...
