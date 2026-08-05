from embedding import create_embedding

if __name__ == "__main__":
    vector = create_embedding("My name is Piyush.")
    if vector:
        print(f"Vector length: {len(vector)}")
        print(vector[:10])
    else:
        print("Failed to generate embedding.")
