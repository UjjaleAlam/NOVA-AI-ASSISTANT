import chromadb
from sentence_transformers import SentenceTransformer
import os
import json
from pathlib import Path

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "nova_memory"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

client = None
collection = None
embedder = None

def init_semantic_memory():
    global client, collection, embedder
    
    os.makedirs(CHROMA_DIR, exist_ok=True)
    
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    embedder = SentenceTransformer(EMBEDDING_MODEL, device=device)
    print(f"Semantic memory ready on {device}.")
    
    return collection

def add_memory(key, value, metadata=None):
    if collection is None:
        init_semantic_memory()
    
    doc_id = f"memory_{key}"
    text = f"{key}: {value}"
    
    embedding = embedder.encode(text).tolist()
    
    meta = {"key": key, "type": "fact"}
    if metadata:
        meta.update(metadata)
    
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[meta]
    )

def search_memory(query, n_results=5):
    if collection is None:
        init_semantic_memory()
    
    if collection.count() == 0:
        return []
    
    query_embedding = embedder.encode(query).tolist()
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    
    memories = []
    if results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            memories.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
    
    return memories

def delete_memory(key):
    if collection is None:
        init_semantic_memory()
    
    doc_id = f"memory_{key}"
    try:
        collection.delete(ids=[doc_id])
        return True
    except Exception:
        return False

def get_all_memories():
    if collection is None:
        init_semantic_memory()
    
    results = collection.get(include=["documents", "metadatas"])
    memories = {}
    if results["documents"]:
        for i, doc in enumerate(results["documents"]):
            meta = results["metadatas"][i]
            key = meta.get("key", f"item_{i}")
            memories[key] = doc
    return memories

if __name__ == "__main__":
    init_semantic_memory()
    add_memory("test", "Nova is an AI operating system")
    print(search_memory("AI operating system"))