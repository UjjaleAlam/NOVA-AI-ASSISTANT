from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):

    # ===========================
    # Voice
    # ===========================

    wake_word = Signal(str)

    command_received = Signal(str)

    listening_started = Signal()

    listening_stopped = Signal()

    # ===========================
    # Speech
    # ===========================

    speak = Signal(str)

    speaking_started = Signal()

    speaking_finished = Signal()

    # ===========================
    # Overlay
    # ===========================

    show_files = Signal(list)

    hide_overlay = Signal()

    update_status = Signal(str)

    update_title = Signal(str)

    # ===========================
    # AI
    # ===========================

    ai_request = Signal(str)

    ai_response = Signal(str)

    # ===========================
    # Startup
    # ===========================

    startup_finished = Signal()

    startup_error = Signal(str)


signal_bus = SignalBus()