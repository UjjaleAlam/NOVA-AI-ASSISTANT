import speech_recognition as sr
import ollama
import socket
import asyncio
import edge_tts

async def test_edge_tts():
    communicate = edge_tts.Communicate("Test", "en-US-AndrewNeural")
    await communicate.save("test_tts.mp3")
    import os
    os.remove("test_tts.mp3")

def startup_check():

    print("\n===== NOVA STARTUP CHECK =====\n")

    # Speaker Test (Edge TTS)
    try:
        asyncio.run(test_edge_tts())
        print("✓ Speaker detected (Edge TTS)")
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