import json
import os

MEMORY_FILE = "memory.json"


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


def recall(key):

    memory = load_memory()

    return memory.get(key)


def all_memory():

    return load_memory()