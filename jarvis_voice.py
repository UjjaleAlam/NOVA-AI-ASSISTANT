import speech_recognition as sr

from brain import ask_jarvis
from voice import speak
from commands import run_command

recognizer = sr.Recognizer()

speak("Jarvis online")

while True:

    with sr.Microphone() as source:

        print("Listening...")

        recognizer.adjust_for_ambient_noise(source, duration=0.5)

        audio = recognizer.listen(source)

    try:

        query = recognizer.recognize_google(audio)

        print(f"\nYou: {query}")

        if query.lower() == "exit":

            speak("Goodbye")
            break

        # Run commands first
        result = run_command(query)

        if result:

            print(f"\nJarvis: {result}")

            speak(result)

            continue

        # Otherwise ask AI
        answer = ask_jarvis(query)

        print(f"\nJarvis: {answer}")

        speak(answer)

    except Exception as e:

        print("Error:", e)