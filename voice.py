import asyncio
import os
import time

import edge_tts
import pygame


VOICE = "en-US-AndrewNeural"

pygame.mixer.init()


async def generate_voice(text, filename):

    communicate = edge_tts.Communicate(
        text=str(text),
        voice=VOICE
    )

    await communicate.save(filename)


def speak(text):

    filename = "jarvis_voice.mp3"

    try:

        asyncio.run(
            generate_voice(
                text,
                filename
            )
        )

        pygame.mixer.music.load(filename)

        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():

            time.sleep(0.02)

        pygame.mixer.music.stop()

        pygame.mixer.music.unload()

    finally:

        try:
            os.remove(filename)
        except Exception:
            pass