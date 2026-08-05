#!/usr/bin/env python3
"""Test script for SON V3 hardware optimization imports."""
import sys
import numpy as np

print("=" * 50)
print("  SON V3 — Hardware Optimization Import Test")
print("=" * 50)
print()

errors = []

# 1. Native acceleration
try:
    from native.son_native import fast_rms, fast_resample, fast_chunk_text, fast_sha256_hex, get_backend_info
    info = get_backend_info()
    backend = info["backend"]
    native = info["native_available"]
    print(f"  [OK] Native: {backend} (C extension: {native})")

    # Test fast_rms
    audio = np.random.randn(48000).astype(np.float32)
    rms = fast_rms(audio)
    print(f"  [OK] fast_rms: {rms:.6f}")

    # Test fast_resample
    resampled = fast_resample(audio, 48000, 16000)
    print(f"  [OK] fast_resample: {len(audio)} -> {len(resampled)} samples")

    # Test fast_chunk_text
    text = "line1\nline2\nline3\nline4\nline5"
    chunks = fast_chunk_text(text, 15, 5)
    print(f"  [OK] fast_chunk_text: {len(chunks)} chunks")

    # Test fast_sha256_hex
    h = fast_sha256_hex("test")
    print(f"  [OK] fast_sha256_hex: {h}")
except Exception as e:
    errors.append(f"Native: {e}")
    print(f"  [FAIL] Native: {e}")

print()

# 2. Pipeline
try:
    from core.pipeline import Pipeline
    print(f"  [OK] Pipeline: {Pipeline.IO_WORKERS} IO, {Pipeline.CPU_WORKERS} CPU workers")
except Exception as e:
    errors.append(f"Pipeline: {e}")
    print(f"  [FAIL] Pipeline: {e}")

# 3. GPU Manager
try:
    from core.gpu_manager import GPUManager
    gpu = GPUManager()
    metrics = gpu.get_metrics()
    name = metrics.get("gpu_name", "Unknown")
    used = metrics.get("vram_used_mb", 0)
    total = metrics.get("vram_total_mb", 0)
    print(f"  [OK] GPUManager: {name} | VRAM: {used:.0f}/{total:.0f} MB")
except Exception as e:
    errors.append(f"GPUManager: {e}")
    print(f"  [FAIL] GPUManager: {e}")

# 4. Cache
try:
    from core.cache import EmbeddingCache, CodeChunkCache
    ec = EmbeddingCache(max_size_mb=100)
    ec.put("test", [1.0, 2.0, 3.0])
    result = ec.get("test")
    assert result == [1.0, 2.0, 3.0], "Cache retrieval mismatch"
    stats = ec.stats()
    print(f"  [OK] EmbeddingCache: {stats['entries']} entries, {stats['size_mb']} MB")

    cc = CodeChunkCache(max_size_mb=100)
    print(f"  [OK] CodeChunkCache: initialized")
except Exception as e:
    errors.append(f"Cache: {e}")
    print(f"  [FAIL] Cache: {e}")

print()

# 5. Benchmark: RMS speed
try:
    import timeit
    audio = np.random.randn(48000).astype(np.float32)

    # NumPy baseline
    t_numpy = timeit.timeit(
        lambda: float(np.sqrt(np.mean(audio ** 2))),
        number=10000
    )

    # Our fast_rms (NumPy fallback or C)
    from native.son_native import fast_rms
    t_fast = timeit.timeit(
        lambda: fast_rms(audio),
        number=10000
    )

    print(f"  Benchmark: RMS (10000 iterations, 48000 samples)")
    print(f"    NumPy:    {t_numpy:.4f}s")
    print(f"    fast_rms: {t_fast:.4f}s")
    ratio = t_numpy / t_fast if t_fast > 0 else 0
    print(f"    Speedup:  {ratio:.1f}x")
except Exception as e:
    print(f"  [SKIP] Benchmark: {e}")

print()

# Summary
if errors:
    print(f"RESULT: {len(errors)} error(s)")
    for err in errors:
        print(f"  - {err}")
else:
    print("RESULT: ALL TESTS PASSED")

sys.exit(len(errors))
