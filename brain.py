import ollama
import time
from commands import run_command

SYSTEM_PROMPT = """
You are Nova, voice assistant.

Rules:
- Give short spoken answers.
- Never use markdown.
- Never use code blocks.
- Keep answers under 3 sentences.
- Speak naturally.
"""


def ask_jarvis(prompt):

    # ---------- COMMAND ROUTER ----------

    command_response = run_command(prompt)

    if command_response is not None:
        return command_response

    # ---------- AI ----------

    start = time.time()

    response = ollama.chat(
        model="qwen3:8b",
        options={
            "num_predict": 80,
            "temperature": 0.5
        },
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

    print(
        f"AI Response Time: {time.time() - start:.2f}s"
    )

    answer = response["message"]["content"]

    if "</think>" in answer:
        answer = answer.split("</think>")[-1]

    return answer.strip()