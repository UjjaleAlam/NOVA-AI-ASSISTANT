import json
import os
from core.semantic_memory import init_semantic_memory, add_memory, search_memory, delete_memory, get_all_memories

MEMORY_FILE = "memory.json"

# Initialize semantic memory on import
init_semantic_memory()


def load_memory():

    if not os.path.exists(MEMORY_FILE):

        with open(MEMORY_FILE, "w") as f:
            json.dump({}, f)

    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(memory):

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)


def remember(key, value):

    memory = load_memory()

    memory[key] = value

    save_memory(memory)
    
    # Also store in semantic memory
    add_memory(key, value)


def recall(key):

    memory = load_memory()

    value = memory.get(key)
    if value:
        return value
    
    # Also check semantic memory
    from core.semantic_memory import collection
    if collection:
        results = collection.get(
            ids=[f"memory_{key}"],
            include=["documents"]
        )
        if results["documents"]:
            doc = results["documents"][0]
            # doc format: "key: value"
            if ": " in doc:
                return doc.split(": ", 1)[1]
            return doc
    
    return None


def all_memory():

    return load_memory()


def search_memory_facts(query, n_results=5):
    """Semantic search over remembered facts."""
    return search_memory(query, n_results)


def forget(key):
    """Remove a memory from both stores."""
    memory = load_memory()
    if key in memory:
        del memory[key]
        save_memory(memory)
    delete_memory(key)
    return True