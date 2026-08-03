from embedding import create_embedding

vector = create_embedding("My name is Piyush.")

print(f"Vector length: {len(vector)}")
print(vector[:10])
