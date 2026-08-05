import chromadb

if __name__ == "__main__":
    client = chromadb.PersistentClient(path="./memory")
    collection = client.get_or_create_collection(
        name="son_memory"
    )
    print("ChromaDB initialized. Collections:", [c.name for c in client.list_collections()])