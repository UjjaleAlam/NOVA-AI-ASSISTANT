import sys

from PySide6.QtWidgets import QApplication

from core.voice_worker import create_voice_thread
from core.command_dispatcher import CommandDispatcher
from core.signal_bus import signal_bus

from ui.overlay_manager import overlay_manager


class NovaApplication:

    def __init__(self):

        self.app = QApplication.instance()

        if self.app is None:

            self.app = QApplication(sys.argv)

        # Keep these alive
        self.dispatcher = CommandDispatcher()

        self.voice_thread = None
        self.voice_worker = None

        self.setup()

    # =====================================================

    def setup(self):

        self.voice_thread, self.voice_worker = create_voice_thread()

        signal_bus.hide_overlay.connect(
            overlay_manager.hide
        )

    # =====================================================

    def run(self):

        print("=================================")
        print("        NOVA AI SYSTEM")
        print("=================================")

        self.voice_thread.start()

    # =====================================================

    def shutdown(self):

        if self.voice_worker:

            self.voice_worker.stop()

        if self.voice_thread:

            self.voice_thread.quit()
            self.voice_thread.wait()