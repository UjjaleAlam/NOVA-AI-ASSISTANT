from brain import ask_jarvis
from voice import speak

print("Jarvis Online")
print("Type 'exit' to quit")

while True:

    user_input = input("\nYou: ")

    if user_input.lower() == "exit":
        speak("Goodbye")
        break

    answer = ask_jarvis(user_input)

    speak(answer)