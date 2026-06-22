from listener import listen
from voice import speak
from commands import run_command
from brain import ask_jarvis
from startup_assistant import startup_message

import time

print("Jarvis Online")

speak(startup_message())

wake_words = [
    "jarvis",
    "hey jarvis"
]

while True:

    print("\nWaiting for wake word...")

    query = listen()

    if not query:
        continue

    print("Wake Word Heard:", query)

    if not any(
        word in query
        for word in wake_words
    ):
        continue

    speak("Yes Ujjale")

    time.sleep(1)

    print("Waiting for command...")

    command = listen()

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

        print("Jarvis:", result)

        speak(result)

        continue

    answer = ask_jarvis(command)

    answer = str(answer)

    if "</think>" in answer:
        answer = answer.split("</think>")[-1]

    answer = answer.strip()

    print("Jarvis:", answer)

    speak(answer[:200])