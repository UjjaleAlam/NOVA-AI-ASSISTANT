import speech_recognition as sr

recognizer = sr.Recognizer()

recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300
recognizer.pause_threshold = 0.8
recognizer.non_speaking_duration = 0.3

# Calibrate once at startup
with sr.Microphone() as source:
    print("Calibrating microphone...")
    recognizer.adjust_for_ambient_noise(
        source,
        duration=2
    )


def listen():

    try:

        with sr.Microphone() as source:

            print("Listening...")

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=20
            )

        text = recognizer.recognize_google(audio)

        print("Recognized:", text)

        return text.lower()

    except sr.WaitTimeoutError:
        return ""

    except Exception as e:

        print(
            "Listen Error:", 
            repr(e)
            )

        return ""