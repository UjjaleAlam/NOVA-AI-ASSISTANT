from PySide6.QtCore import QObject, Slot

from commands import run_command
from brain import ask_jarvis

from core.voice_manager import voice_manager
from core.signal_bus import signal_bus


class CommandDispatcher(QObject):

    def __init__(self):

        super().__init__()

        signal_bus.command_received.connect(
            self.handle_command
        )

        signal_bus.speak.connect(
            self.handle_speech
        )

    # ======================================================

    @Slot(str)
    def handle_command(self, command):

        command = command.strip().lower()

        if not command:
            return

        if command in (
            "exit",
            "quit",
            "goodbye"
        ):

            signal_bus.speak.emit("Goodbye")

            from PySide6.QtWidgets import QApplication

            QApplication.quit()

            return

        result = run_command(command)

        if result:

            signal_bus.speak.emit(result)

            return

        answer = ask_jarvis(command)

        answer = str(answer)

        if "</think>" in answer:

            answer = answer.split("</think>")[-1]

        signal_bus.speak.emit(
            answer.strip()
        )

    # ======================================================

    @Slot(str)
    def handle_speech(self, text):

        voice_manager.say(text)