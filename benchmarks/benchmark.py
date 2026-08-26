import sys
import os
import time
from pathlib import Path

# Add project root to path
root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root))

def benchmark_think_latency():
    try:
        from core.brain import Brain
        from core.config import Config
    except ImportError as e:
        print(f"Failed to import SON modules: {e}")
        return

    print("Initializing Brain...")
    # Mocking memory and other components for isolation
    brain = Brain()
    
    queries = [
        "What's the weather like today?",
        "List my recent files",
        "Explain this code: def hello(): pass",
        "Who is the president of the United States?",
        "Can you help me write a python script?",
    ] * 2  # Run each a few times to test cache and performance
    
    latencies = []
    print(f"Starting benchmark with {len(queries)} queries...")
    
    for i, q in enumerate(queries):
        start = time.perf_counter()
        print(f"Query {i+1}: {q[:30]}...")
        result = brain.think(q)
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)
        print(f"  -> Latency: {latency:.2f}ms | Response length: {len(result)}")
    
    if latencies:
        print("\n--- Results ---")
        print(f"Total queries: {len(latencies)}")
        print(f"Avg latency: {sum(latencies)/len(latencies):.2f}ms")
        
        sorted_latencies = sorted(latencies)
        print(f"P50 latency: {sorted_latencies[len(latencies)//2]:.2f}ms")
        print(f"P95 latency: {sorted_latencies[int(len(latencies)*0.95)]:.2f}ms")
        print(f"Max latency: {sorted_latencies[-1]:.2f}ms")
        print(f"Min latency: {sorted_latencies[0]:.2f}ms")

if __name__ == "__main__":
    benchmark_think_latency()
