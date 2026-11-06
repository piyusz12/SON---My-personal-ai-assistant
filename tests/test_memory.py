import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from memory import Memory


def test_memory_store_and_recall():
    mem = Memory()
    mem.store_fact("My favorite language is Python.", category="preferences")
    result = mem.recall("Which programming language do I like?")
    assert result is not None
    assert isinstance(result, list)


if __name__ == "__main__":
    test_memory_store_and_recall()
    print("Memory test passed.")
