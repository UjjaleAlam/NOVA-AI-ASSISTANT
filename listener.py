import speech_recognition as sr

recognizer = sr.Recognizer()

def listen():

    try:

        with sr.Microphone() as source:

            print("Listening...")

            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.5
            )

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=10
            )

        text = recognizer.recognize_google(audio)

        print("Recognized:", text)

        return text.lower()

    except Exception as e:

        print("Listen Error:", e)

        return ""