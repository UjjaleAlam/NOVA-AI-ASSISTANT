from listener import listen
from voice import speak
from commands import run_command
from brain import ask_jarvis
from startup_assistant import startup_message

import time

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

    if result:

        print("Nova:", result)

        speak(result)

        continue

    answer = ask_jarvis(command)

    answer = str(answer)

    if "</think>" in answer:
        answer = answer.split("</think>")[-1]

    answer = answer.strip()

    print("Nova:", answer)

    speak(answer[:200])