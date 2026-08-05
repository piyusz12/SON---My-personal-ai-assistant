# native/__init__.py — SON V3 Native Acceleration Package
"""
Native C/C++ acceleration layer for SON V3.
Provides SIMD-optimized functions for audio processing, text chunking, and hashing.

Build:
    native\\build.bat    (Windows)
    python native/setup.py build_ext --inplace  (cross-platform)

Usage:
    from native.son_native import fast_rms, fast_resample, fast_chunk_text
"""
from native.son_native import (
    fast_rms,
    fast_resample,
    fast_chunk_text,
    fast_sha256_hex,
    fast_audio_energy,
    is_native_available,
    get_backend_info,
)

__all__ = [
    "fast_rms",
    "fast_resample",
    "fast_chunk_text",
    "fast_sha256_hex",
    "fast_audio_energy",
    "is_native_available",
    "get_backend_info",
]
