import speech_recognition as sr
import pyttsx3
import ollama
import socket

def startup_check():

    print("\n===== JARVIS STARTUP CHECK =====\n")

    # Speaker Test
    try:
        engine = pyttsx3.init()
        print("✓ Speaker detected")
    except Exception as e:
        print("✗ Speaker Error:", e)

    # Microphone Test
    try:
        sr.Microphone()
        print("✓ Microphone detected")
    except Exception as e:
        print("✗ Microphone Error:", e)

    # Ollama Test
    try:
        ollama.list()
        print("✓ Ollama connected")
    except Exception as e:
        print("✗ Ollama Error:", e)

    # Internet Test
    try:
        socket.create_connection(("google.com", 80), timeout=3)
        print("✓ Internet connected")
    except:
        print("✗ No internet connection")

    print("\n===============================\n")