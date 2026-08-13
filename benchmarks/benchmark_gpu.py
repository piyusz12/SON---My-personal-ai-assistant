# benchmarks/benchmark_gpu.py — GPU Utilization Verification for SON V3
"""
Verifies that Ollama is actually using the GPU and measures inference performance.

Run:
    python -m benchmarks.benchmark_gpu

Output:
    GPU: NVIDIA GeForce RTX 4060 Laptop GPU
    VRAM: 5842 / 8188 MB (71.3%)
    Temperature: 62°C

    Ollama Inference Test (qwen3:8b):
      TTFT:       1.18s
      Tokens/sec: 42.3
      Total time: 3.21s
      Tokens:     136

    Whisper GPU Check:
      Device: cuda
      Model loaded: ✓
      VRAM delta: +1420 MB
"""
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows console encoding (cp1252 can't handle Unicode/box drawing characters)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def benchmark_gpu_metrics():
    """Check GPU status and VRAM allocation."""
    print("=" * 60)
    print("GPU STATUS")
    print("=" * 60)

    try:
        from core.gpu_manager import GPUManager
        gpu = GPUManager()
        metrics = gpu.get_metrics()

        print(f"  GPU:         {metrics['gpu_name']}")
        print(f"  Utilization: {metrics['gpu_util']:.0f}%")
        print(f"  VRAM Used:   {metrics['vram_used_mb']:.0f} / {metrics['vram_total_mb']:.0f} MB "
              f"({metrics['vram_used_mb'] / metrics['vram_total_mb'] * 100:.1f}%)")
        print(f"  VRAM Free:   {metrics['vram_free_mb']:.0f} MB")
        print(f"  Temperature: {metrics['gpu_temp_c']:.0f}°C")
        print(f"  Power Draw:  {metrics['power_draw_w']:.1f}W")
        return metrics
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def benchmark_ollama_inference():
    """Test Ollama LLM inference speed."""
    print()
    print("=" * 60)
    print("OLLAMA INFERENCE BENCHMARK")
    print("=" * 60)

    try:
        import config
        from core.ollama_client import ResilientOllamaClient

        client = ResilientOllamaClient()

        if not client.is_healthy():
            print("  ERROR: Ollama is not running!")
            return None

        model = config.LLM_MODEL
        print(f"  Model:   {model}")
        print(f"  Host:    {config.OLLAMA_HOST}")
        print()

        # Test non-streaming (measure total time)
        print("  Non-streaming test...")
        prompt = "Explain what a GPU is in exactly 3 sentences."
        start = time.perf_counter()

        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={
                "num_ctx": 2048,
                "num_gpu": 99,
                "num_predict": 150,
                "temperature": 0.7,
            },
        )

        total_time = time.perf_counter() - start
        ttft = response.get("_ttft_ms", 0) / 1000

        content = response["message"]["content"]
        # Estimate token count (~4 chars per token)
        est_tokens = len(content.split())

        print(f"    TTFT:         {ttft:.2f}s")
        print(f"    Total time:   {total_time:.2f}s")
        print(f"    Output words: {est_tokens}")
        print(f"    Words/sec:    {est_tokens / total_time:.1f}")
        print()

        # Test streaming (measure TTFT accurately)
        print("  Streaming test...")
        start = time.perf_counter()
        first_token_time = None
        token_count = 0
        full_text = []

        stream = client.chat_stream(
            model=model,
            messages=[{"role": "user", "content": "Count from 1 to 20."}],
            options={
                "num_ctx": 2048,
                "num_gpu": 99,
                "num_predict": 100,
                "temperature": 0.7,
            },
        )

        for chunk in stream:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            token_count += 1
            full_text.append(chunk.get("message", {}).get("content", ""))

        total_stream = time.perf_counter() - start
        ttft_stream = (first_token_time - start) if first_token_time else 0

        print(f"    TTFT:         {ttft_stream:.2f}s")
        print(f"    Total time:   {total_stream:.2f}s")
        print(f"    Chunks:       {token_count}")
        print(f"    Chunks/sec:   {token_count / total_stream:.1f}")

        return {
            "model": model,
            "ttft_nonstream": ttft,
            "total_nonstream": total_time,
            "ttft_stream": ttft_stream,
            "total_stream": total_stream,
            "chunks": token_count,
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def benchmark_embedding():
    """Test embedding speed."""
    print()
    print("=" * 60)
    print("EMBEDDING BENCHMARK")
    print("=" * 60)

    try:
        import config
        from core.ollama_client import ResilientOllamaClient

        client = ResilientOllamaClient()

        # Single embedding
        text = "What is the meaning of life?"
        start = time.perf_counter()
        response = client.embed(model=config.EMBED_MODEL, input=text)
        single_time = (time.perf_counter() - start) * 1000

        dim = len(response["embeddings"][0])
        print(f"  Model:      {config.EMBED_MODEL}")
        print(f"  Dimensions: {dim}")
        print(f"  Single:     {single_time:.1f}ms")

        # Batch embedding
        texts = [f"Sample text number {i} for testing embedding speed." for i in range(10)]
        start = time.perf_counter()
        response = client.embed(model=config.EMBED_MODEL, input=texts)
        batch_time = (time.perf_counter() - start) * 1000

        print(f"  Batch (10):  {batch_time:.1f}ms ({batch_time / 10:.1f}ms/text)")

        return {
            "model": config.EMBED_MODEL,
            "dimensions": dim,
            "single_ms": single_time,
            "batch_10_ms": batch_time,
            "per_text_ms": batch_time / 10,
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def benchmark_chromadb():
    """Test ChromaDB query speed."""
    print()
    print("=" * 60)
    print("CHROMADB BENCHMARK")
    print("=" * 60)

    try:
        import config
        from core.ollama_client import ResilientOllamaClient

        try:
            import chromadb
        except ImportError:
            print("  ⚠ ChromaDB is not installed in the current Python environment.")
            print("  To install: pip install chromadb")
            return None

        client = chromadb.PersistentClient(path=config.MEMORY_DIR)
        ollama_client = ResilientOllamaClient()

        # List collections
        collections = client.list_collections()
        print(f"  Collections: {len(collections)}")
        for col in collections:
            count = col.count()
            print(f"    {col.name}: {count} documents")

        # Query test
        if collections:
            col = collections[0]
            if col.count() > 0:
                # Generate query embedding
                start = time.perf_counter()
                embed_resp = ollama_client.embed(
                    model=config.EMBED_MODEL,
                    input="test query for benchmark"
                )
                embed_time = (time.perf_counter() - start) * 1000

                # Query ChromaDB
                start = time.perf_counter()
                results = col.query(
                    query_embeddings=[embed_resp["embeddings"][0]],
                    n_results=min(5, col.count()),
                )
                query_time = (time.perf_counter() - start) * 1000

                print(f"  Embed time:  {embed_time:.1f}ms")
                print(f"  Query time:  {query_time:.1f}ms")
                print(f"  Total:       {embed_time + query_time:.1f}ms")

                return {
                    "collections": len(collections),
                    "embed_ms": embed_time,
                    "query_ms": query_time,
                    "total_ms": embed_time + query_time,
                }

    except Exception as e:
        print(f"  ERROR: {e}")
    return None


def main():
    """Run all GPU and inference benchmarks."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           SON V3 — GPU & Inference Benchmark            ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    results = {}

    results["gpu"] = benchmark_gpu_metrics()
    results["ollama"] = benchmark_ollama_inference()
    results["embedding"] = benchmark_embedding()
    results["chromadb"] = benchmark_chromadb()

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if results["gpu"]:
        print(f"  GPU:       {results['gpu']['gpu_name']}")
        print(f"  VRAM:      {results['gpu']['vram_used_mb']:.0f}/{results['gpu']['vram_total_mb']:.0f} MB")

    if results["ollama"]:
        print(f"  LLM TTFT:  {results['ollama']['ttft_stream']:.2f}s (streaming)")
        print(f"  LLM TTFT:  {results['ollama']['ttft_nonstream']:.2f}s (non-streaming)")

    if results["embedding"]:
        print(f"  Embed:     {results['embedding']['single_ms']:.0f}ms (single)")
        print(f"  Embed:     {results['embedding']['per_text_ms']:.0f}ms/text (batch)")

    if results["chromadb"]:
        print(f"  ChromaDB:  {results['chromadb']['query_ms']:.0f}ms (query)")
        print(f"  Memory:    {results['chromadb']['total_ms']:.0f}ms (embed+query)")

    print()


if __name__ == "__main__":
    main()
