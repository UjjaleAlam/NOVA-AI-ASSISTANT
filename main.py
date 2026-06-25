from threading import Thread

from brain import ask_jarvis
from voice import speak
from watchdog_manager import start_watchdog

print("Novaine")
print("Type 'exit' to quit")

Thread(
    target=start_watchdog,
    daemon=True
).start()

while True:

    user_input = input("\nYou: ")

    if user_input.lower() == "exit":
        speak("Goodbye")
        break

    answer = ask_jarvis(user_input)

    speak(answer)