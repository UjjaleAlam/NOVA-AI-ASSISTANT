import ollama
def ask_jarvis(prompt):
    response = ollama.chat(
        model="qwen3:8b",
        messages=[
            {"role":"user",
             "content": prompt
             }
        ]
    )

    return response["message"]["content"]