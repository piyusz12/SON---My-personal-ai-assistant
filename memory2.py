from embedding import create_embedding
from chroma_db import collection


def remember(memory_id: str, text: str):

    embedding = create_embedding(text)

    collection.add(
        ids=[memory_id],
        documents=[text],
        embeddings=[embedding]
    )


def recall(query: str):

    embedding = create_embedding(query)

    result = collection.query(
        query_embeddings=[embedding],
        n_results=3
    )

    return result