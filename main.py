import sys
from PySide6.QtWidgets import QApplication

from core.application import NovaApplication


def main():

    app = QApplication.instance()

    if app is None:
        app = QApplication(sys.argv)

    nova = NovaApplication()

    nova.run()

    exit_code = app.exec()

    nova.shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()