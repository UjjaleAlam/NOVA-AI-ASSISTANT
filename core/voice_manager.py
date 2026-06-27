from queue import Queue
from threading import Thread

from core.signal_bus import signal_bus
from voice import speak


class VoiceManager:

    def __init__(self):

        self.queue = Queue()

        self.worker = Thread(
            target=self.run,
            daemon=True
        )

        self.worker.start()

    # ======================================

    def run(self):

        while True:

            text = self.queue.get()

            signal_bus.speaking_started.emit()

            try:

                speak(text)

            except Exception as e:

                print("Voice:", e)

            signal_bus.speaking_finished.emit()

            self.queue.task_done()

    # ======================================

    def say(self, text):

        if text:

            self.queue.put(str(text))


voice_manager = VoiceManager()