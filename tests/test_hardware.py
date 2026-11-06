#!/usr/bin/env python3
"""Test script for SON V3 hardware optimization imports."""
import os
import sys
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 50)
print("  SON V3 — Hardware Optimization Import Test")
print("=" * 50)
print()

def test_hardware_components():
    """Verify hardware acceleration components and caches."""
    errors = []
    
    # 1. Native acceleration
    try:
        from native.son_native import fast_rms, fast_resample, fast_chunk_text, fast_sha256_hex, get_backend_info
        backend = get_backend_info()
        print(f"  [OK] Native: {backend}")

        audio = np.random.randn(48000).astype(np.float32)
        rms = fast_rms(audio)
        print(f"  [OK] fast_rms: {rms:.6f}")

        resampled = fast_resample(audio, 48000, 16000)
        print(f"  [OK] fast_resample: {len(audio)} -> {len(resampled)} samples")

        text = "line1\nline2\nline3\nline4\nline5"
        chunks = fast_chunk_text(text, 15, 5)
        print(f"  [OK] fast_chunk_text: {len(chunks)} chunks")

        h = fast_sha256_hex("test")
        print(f"  [OK] fast_sha256_hex: {h}")
    except Exception as e:
        errors.append(f"Native: {e}")

    # 2. Pipeline
    try:
        from core.pipeline import Pipeline
        print(f"  [OK] Pipeline: {Pipeline.IO_WORKERS} IO, {Pipeline.CPU_WORKERS} CPU workers")
    except Exception as e:
        errors.append(f"Pipeline: {e}")

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

    # 4. Cache
    try:
        from core.cache import EmbeddingCache, CodeChunkCache
        ec = EmbeddingCache(max_size_mb=100)
        ec.put("test", [1.0, 2.0, 3.0])
        result = ec.get("test")
        assert result == [1.0, 2.0, 3.0], "Cache retrieval mismatch"
        stats = ec.stats()
        entries = stats.get("embedding_cache", {}).get("entries", stats.get("entries", 0))
        size_mb = stats.get("total_size_mb", stats.get("size_mb", 0))
        print(f"  [OK] EmbeddingCache: {entries} entries, {size_mb} MB")

        cc = CodeChunkCache(max_size_mb=100)
        print(f"  [OK] CodeChunkCache: initialized")
    except Exception as e:
        errors.append(f"Cache: {e}")

    assert len(errors) == 0, f"Hardware component errors: {errors}"


if __name__ == "__main__":
    test_hardware_components()
    print("RESULT: ALL TESTS PASSED")
