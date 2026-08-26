import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import time
from core.intent_router import IntentRouter

def test_intent():
    router = IntentRouter()
    
    test_cases = [
        "open github.com",
        "set volume to 50",
        "hi",
        "search google for dogs",
        "can you help me write a python script?", # Complex fallback
    ]
    
    print("Testing Native Intent Classification Latency:\n")
    for text in test_cases:
        start = time.perf_counter()
        res = router.classify(text)
        latency_us = (time.perf_counter() - start) * 1_000_000
        
        print(f"Input: {text}")
        print(f"  -> Intent: {res.intent.name} ({res.subcategory})")
        print(f"  -> Matched via: {res.matched_pattern}")
        print(f"  -> Latency: {latency_us:.2f} µs\n")

if __name__ == "__main__":
    test_intent()
