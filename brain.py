import ollama

SYSTEM_PROMPT = """
You are Jarvis, a voice assistant.

Rules:
- Give short spoken answers.
- Never use markdown.
- Never use code blocks.
- Never use bullet points unless requested.
- Keep answers under 3 sentences.
- Speak naturally.
"""

def ask_jarvis(prompt):

    response = ollama.chat(
        model="qwen3:8b",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    answer = response["message"]["content"]

    if "</think>" in answer:
        answer = answer.split("</think>")[-1]

    return answer.strip()