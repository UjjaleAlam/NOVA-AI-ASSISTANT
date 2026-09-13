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


def ask_nova(prompt):

    # ---------- AI ----------

    start = time.time()

    try:
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
    except Exception as e:
        return f"AI service unavailable: {e}"

    print(
        f"AI Response Time: {time.time() - start:.2f}s"
    )

    answer = response["message"]["content"]

    # qwen3 models put response in 'thinking' field when content is empty
    if not answer and response["message"].get("thinking"):
        answer = response["message"]["thinking"]

    if "回答" in answer:
        answer = answer.split("回答")[-1]

    return answer.strip()