import pyttsx3

engine = pyttsx3.init()

print("Speaking...")
engine.say("Hello. This is a voice test.")
engine.runAndWait()

print("Done")