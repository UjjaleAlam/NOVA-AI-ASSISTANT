from core.signal_bus import signal_bus


class StartupManager:

    def __init__(self):

        self.tasks = []

    # =====================================================

    def register(self, task):

        self.tasks.append(task)

    # =====================================================

    def start(self):

        for task in self.tasks:

            try:

                task()

            except Exception as e:

                signal_bus.startup_error.emit(str(e))

                return False

        signal_bus.startup_finished.emit()

        return True


startup_manager = StartupManager()