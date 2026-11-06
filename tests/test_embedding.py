import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embedding import create_embedding

if __name__ == "__main__":
    vector = create_embedding("My name is Piyush.")
    if vector:
        print(f"Vector length: {len(vector)}")
        print(vector[:10])
    else:
        print("Failed to generate embedding.")
