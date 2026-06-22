import pyttsx3

def speak(text):
    engine = pyttsx3.init()

    voices = engine.getProperty("voices")
    engine.setProperty("voice", voices[1].id)  # Zira
    engine.setProperty("rate", 180)

    engine.say(str(text))
    engine.runAndWait()

    engine.stop()