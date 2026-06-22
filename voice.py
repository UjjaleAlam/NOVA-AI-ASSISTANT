import asyncio
import edge_tts
import pygame
import os
import time

VOICE = "en-US-AndrewNeural"


async def generate_voice(text):

    communicate = edge_tts.Communicate(
        text=str(text),
        voice=VOICE
    )

    await communicate.save("jarvis_voice.mp3")


def speak(text):

    try:

        text = str(text)

        asyncio.run(generate_voice(text))

        pygame.mixer.init()

        pygame.mixer.music.load(
            "jarvis_voice.mp3"
        )

        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():

            time.sleep(0.1)

        pygame.mixer.quit()

        try:
            os.remove("jarvis_voice.mp3")
        except:
            pass

    except Exception as e:

        print("Voice Error:", e)