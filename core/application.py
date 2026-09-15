import sys
import threading

from PySide6.QtWidgets import QApplication

from core.voice_worker import create_voice_thread
from core.command_dispatcher import CommandDispatcher
from core.signal_bus import signal_bus
from core.logging_config import setup_logging, get_logger
from core.monitor import system_monitor
from core.recovery import recovery_manager
from core.multi_agent import orchestrator

from ui.overlay_manager import overlay_manager

from watchdog_manager import start_watchdog


class NovaApplication:

    def __init__(self):

        self.logger = get_logger("application")
        setup_logging()
        
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

        threading.Thread(
            target=start_watchdog,
            daemon=True
        ).start()

        signal_bus.hide_overlay.connect(
            overlay_manager.hide
        )
        
        system_monitor.register_callback(self._on_system_issue)
        system_monitor.start()
        
        # Start multi-agent orchestrator
        orchestrator.start()
        
        self.logger.info("Nova application initialized")

    # =====================================================

    def _on_system_issue(self, issue):
        self.logger.warning(f"System issue detected: {issue}")
        signal_bus.speak.emit(f"System warning: {issue}")

    # =====================================================

    def run(self):

        print("=================================")
        print("        NOVA AI SYSTEM")
        print("=================================")

        self.voice_thread.start()

    # =====================================================

    def shutdown(self):

        self.logger.info("Shutting down Nova...")
        system_monitor.stop()
        
        # Stop multi-agent orchestrator
        orchestrator.stop()
        
        if self.voice_worker:

            self.voice_worker.stop()

        if self.voice_thread:

            self.voice_thread.quit()
            self.voice_thread.wait()