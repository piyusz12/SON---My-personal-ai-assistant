import chromadb

client = chromadb.PersistentClient(path="./memory")

collection = client.get_or_create_collection(
    name="son_memory"
)