import speech_recognition as sr

recognizer = sr.Recognizer()

recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.6
recognizer.phrase_threshold = 0.3


def listen():

    try:

        with sr.Microphone() as source:

            print("Listening...")

            audio = recognizer.listen(
                source,
                timeout=8,
                phrase_time_limit=None
            )

        text = recognizer.recognize_google(
            audio,
            language="en-US"
        )

        print("Recognized:", text)

        return text.lower()

    except Exception as e:

        print("Listen Error:", e)

        return ""