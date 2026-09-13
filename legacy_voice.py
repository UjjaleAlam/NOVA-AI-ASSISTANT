from listener import listen
from voice import speak
from commands import run_command
from brain import ask_nova
from startup_assistant import startup_message
from PySide6.QtWidgets import QApplication
import sys


import time

app = QApplication.instance()

if app is None:
    app = QApplication(sys.argv)

print("Nova Online")

speak(startup_message())

wake_words = [
    "nova",
    "hey nova"
]

while True:

    print("\nWaiting for wake word...")

    query = listen()

    if not query:
        continue

    print("Wake Word Heard:", query)

    if "nova" not in query:
        continue

    command = query.replace("nova", "").strip()


    if not command:
        continue

    print("Command:", command)

    if command in [
        "exit",
        "quit",
        "goodbye"
    ]:

        speak("Goodbye")
        break

    result = run_command(command)

    app.processEvents()

    if result:

        print("Nova:", result)

        speak(result)

        continue

    answer = ask_nova(command)

    answer = str(answer)

    if "</think>" in answer:
        answer = answer.split("</think>")[-1]

    answer = answer.strip()

    print("Nova:", answer)

    # Trim at sentence boundary to avoid cutting mid-sentence
    def trim_at_sentence(text, max_len=200):
        if len(text) <= max_len:
            return text
        trimmed = text[:max_len]
        last_period = trimmed.rfind('.')
        last_question = trimmed.rfind('?')
        last_exclaim = trimmed.rfind('!')
        last_sentence_end = max(last_period, last_question, last_exclaim)
        if last_sentence_end > 0:
            return trimmed[:last_sentence_end + 1]
        return trimmed

    speak(trim_at_sentence(answer))

    app.processEvents()