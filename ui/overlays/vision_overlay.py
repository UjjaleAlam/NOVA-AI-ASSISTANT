from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.overlay import NovaOverlay


class VisionOverlay(NovaOverlay):

    def __init__(self):

        super().__init__()

        self.container = QWidget(self)

        self.container.resize(
            self.width(),
            self.height()
        )

        self.container.setStyleSheet("""

        QWidget{

            background:#1E1E1E;

            border-radius:18px;

            border:1px solid #444;

            color:white;

        }

        """)

        layout = QVBoxLayout(self.container)

        # -------------------------------------------------

        self.title = QLabel("Vision")

        self.title.setAlignment(
            Qt.AlignCenter
        )

        self.title.setStyleSheet("""

            font-size:22px;

            font-weight:bold;

            padding:10px;

        """)

        layout.addWidget(self.title)

        # -------------------------------------------------

        self.output = QTextEdit()

        self.output.setReadOnly(True)

        self.output.setStyleSheet("""

        QTextEdit{

            background:#2A2A2A;

            border:none;

            padding:10px;

            font-size:14px;

        }

        """)

        layout.addWidget(self.output)

        # -------------------------------------------------

        self.status = QLabel("Ready")

        self.status.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(self.status)

        # -------------------------------------------------

        close = QPushButton("Close")

        close.clicked.connect(
            self.hide_overlay
        )

        layout.addWidget(close)

    # =====================================================

    def show_message(
        self,
        text,
        title="Vision"
    ):

        self.set_title(title)

        self.output.setPlainText(text)

        self.show_overlay()

    # =====================================================

    def set_status(
        self,
        text
    ):

        self.status.setText(text)

    # =====================================================

    def set_title(
        self,
        text
    ):

        self.title.setText(text)