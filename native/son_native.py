# native/son_native.py — Python API for SON V3 Native Acceleration
"""
Wraps the C extension _son_accel with automatic fallback to
optimized pure-Python (NumPy) implementations if the C module
isn't compiled.

Usage:
    from native.son_native import fast_rms, fast_resample, fast_chunk_text

All functions work identically whether using C or Python backend.
"""
import hashlib
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Try to load C extension ──────────────────────────────────
_NATIVE_AVAILABLE = False
_accel = None

try:
    import _son_accel as _accel
    _NATIVE_AVAILABLE = True
    logger.info("SON Native Acceleration: C extension loaded (AVX2/FMA)")
except ImportError:
    try:
        # Try relative import in case it's in the native package
        from native import _son_accel as _accel
        _NATIVE_AVAILABLE = True
        logger.info("SON Native Acceleration: C extension loaded (package)")
    except ImportError:
        logger.warning(
            "SON Native Acceleration: C extension not available. "
            "Using NumPy fallback. Run 'native/build.bat' to compile for ~50x speedup."
        )


def is_native_available() -> bool:
    """Check if the C extension is loaded."""
    return _NATIVE_AVAILABLE


# ═══════════════════════════════════════════════════════════════
#  fast_rms — Root Mean Square (for VAD)
# ═══════════════════════════════════════════════════════════════

def fast_rms(audio: np.ndarray) -> float:
    """
    Compute RMS amplitude of float32 audio buffer.
    
    Uses AVX2 SIMD when C extension is available (~50x faster).
    Falls back to optimized NumPy (BLAS dot product) otherwise.
    
    Args:
        audio: 1D float32 numpy array of audio samples.
    
    Returns:
        RMS amplitude as float.
    """
    if audio.size == 0:
        return 0.0
    
    if _NATIVE_AVAILABLE:
        # C extension expects raw bytes buffer
        buf = audio.astype(np.float32, copy=False).tobytes()
        return _accel.fast_rms(buf)
    
    # NumPy fallback — use dot product (BLAS-accelerated, single pass)
    flat = audio.ravel()
    return float(np.sqrt(np.dot(flat, flat) / flat.size))


# ═══════════════════════════════════════════════════════════════
#  fast_resample — Audio Sample Rate Conversion
# ═══════════════════════════════════════════════════════════════

def fast_resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """
    Resample float32 audio from src_rate to dst_rate.
    
    Uses linear interpolation (fast, good enough for voice).
    C extension is ~10x faster than scipy.signal.resample.
    
    Args:
        audio: 1D float32 numpy array.
        src_rate: Source sample rate (e.g., 48000).
        dst_rate: Destination sample rate (e.g., 16000).
    
    Returns:
        Resampled float32 numpy array.
    """
    if src_rate == dst_rate:
        return audio
    
    if _NATIVE_AVAILABLE:
        buf = audio.astype(np.float32, copy=False).tobytes()
        result_bytes = _accel.fast_resample(buf, src_rate, dst_rate)
        return np.frombuffer(result_bytes, dtype=np.float32)
    
    # NumPy fallback — linear interpolation
    dst_len = int(len(audio) * dst_rate / src_rate)
    indices = np.linspace(0, len(audio) - 1, dst_len)
    idx_floor = np.floor(indices).astype(np.intp)
    idx_ceil = np.minimum(idx_floor + 1, len(audio) - 1)
    frac = indices - idx_floor
    return (audio[idx_floor] * (1 - frac) + audio[idx_ceil] * frac).astype(np.float32)


# ═══════════════════════════════════════════════════════════════
#  fast_chunk_text — Text Chunking for Codebase Scanner
# ═══════════════════════════════════════════════════════════════

def fast_chunk_text(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    """
    Split text into overlapping chunks by lines.
    
    Args:
        text: Full text content to chunk.
        chunk_size: Target chunk size in characters.
        overlap: Overlap size in characters.
    
    Returns:
        List of (chunk_text, start_line, end_line) tuples.
        Lines are 1-indexed.
    """
    if not text or chunk_size <= 0:
        return []
    
    if _NATIVE_AVAILABLE:
        return _accel.fast_chunk_text(text, chunk_size, overlap)
    
    # Python fallback
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    start_line = 0  # 0-indexed during processing

    for i, line in enumerate(lines):
        current_chunk.append(line)
        current_len += len(line) + 1  # +1 for newline

        if current_len >= chunk_size or i == len(lines) - 1:
            chunk_text = '\n'.join(current_chunk)
            chunks.append((chunk_text, start_line + 1, i + 1))  # 1-indexed

            if i < len(lines) - 1:
                # Calculate overlap
                overlap_lines = []
                overlap_len = 0
                for ln in reversed(current_chunk):
                    overlap_len += len(ln) + 1
                    overlap_lines.insert(0, ln)
                    if overlap_len >= overlap:
                        break

                current_chunk = overlap_lines
                current_len = overlap_len
                start_line = i - len(overlap_lines) + 1

    return chunks


# ═══════════════════════════════════════════════════════════════
#  fast_sha256_hex — Fast Hash for Chunk IDs
# ═══════════════════════════════════════════════════════════════

def fast_sha256_hex(data: str) -> str:
    """
    Compute SHA-256 of string data, return first 16 hex characters.
    
    Args:
        data: String to hash.
    
    Returns:
        16-character hex string.
    """
    if _NATIVE_AVAILABLE:
        return _accel.fast_sha256_hex(data)
    
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════
#  fast_audio_energy — Batch VAD Energy Levels
# ═══════════════════════════════════════════════════════════════

def fast_audio_energy(audio: np.ndarray, chunk_samples: int) -> list[float]:
    """
    Compute per-chunk RMS energy across an entire audio buffer.
    
    Useful for bulk voice activity detection without Python loop overhead.
    
    Args:
        audio: 1D float32 numpy array.
        chunk_samples: Number of samples per chunk.
    
    Returns:
        List of RMS values, one per chunk.
    """
    if audio.size == 0 or chunk_samples <= 0:
        return []
    
    if _NATIVE_AVAILABLE:
        buf = audio.astype(np.float32, copy=False).tobytes()
        return _accel.fast_audio_energy(buf, chunk_samples)
    
    # NumPy fallback
    num_chunks = len(audio) // chunk_samples
    energies = []
    for i in range(num_chunks):
        chunk = audio[i * chunk_samples:(i + 1) * chunk_samples]
        energies.append(float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2))))
    return energies


# ═══════════════════════════════════════════════════════════════
#  Status / Diagnostics
# ═══════════════════════════════════════════════════════════════

def get_backend_info() -> dict:
    """Return information about the active backend."""
    return {
        "native_available": _NATIVE_AVAILABLE,
        "backend": "C (AVX2/FMA)" if _NATIVE_AVAILABLE else "NumPy (Python)",
        "functions": ["fast_rms", "fast_resample", "fast_chunk_text", 
                      "fast_sha256_hex", "fast_audio_energy"],
    }
