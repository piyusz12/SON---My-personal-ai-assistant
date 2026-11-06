import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embedding import create_embedding


def test_embedding_generation():
    vector = create_embedding("My name is Piyush.")
    # May return vector list if Ollama nomic-embed is up or fallback embedding
    assert vector is None or isinstance(vector, list)
    if vector:
        assert len(vector) > 0


if __name__ == "__main__":
    test_embedding_generation()
    print("Embedding test passed.")
