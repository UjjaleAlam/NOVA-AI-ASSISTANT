from PySide6.QtCore import QObject, QThread, Slot

from listener import listen
from core.signal_bus import signal_bus


class VoiceWorker(QObject):

    def __init__(self):

        super().__init__()

        self.running = True

        self.wake_words = [
            "nova",
            "hey nova"
        ]

    # ======================================================

    @Slot()
    def run(self):

        while self.running:

            signal_bus.listening_started.emit()

            query = listen()

            signal_bus.listening_stopped.emit()

            if not query:
                continue

            query = query.lower().strip()

            if not any(
                word in query
                for word in self.wake_words
            ):
                continue

            signal_bus.wake_word.emit(query)

            command = query

            for wake in self.wake_words:
                command = command.replace(
                    wake,
                    ""
                )

            command = command.strip()

            if not command:
                continue

            signal_bus.command_received.emit(
                command
            )

    # ======================================================

    def stop(self):

        self.running = False


# ==========================================================

def create_voice_thread():

    worker = VoiceWorker()

    thread = QThread()

    worker.moveToThread(thread)

    thread.started.connect(
        worker.run
    )

    return thread, worker