import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from memory import Memory

if __name__ == "__main__":
    mem = Memory()
    mem.store_fact("My favorite language is Python.", category="preferences")
    result = mem.recall("Which programming language do I like?")
    print("Recalled facts:", result)