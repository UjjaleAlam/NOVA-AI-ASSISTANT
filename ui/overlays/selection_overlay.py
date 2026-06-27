from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.overlay import NovaOverlay
from ui.models.selection_model import SelectionModel
from ui.delegates.selection_delegate import SelectionDelegate


class SelectionOverlay(NovaOverlay):

    MIN_HEIGHT = 180
    MAX_HEIGHT = 700

    def __init__(self):

        super().__init__()

        self.callback = None

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

        # --------------------------------------------

        self.title = QLabel("NOVA")

        self.title.setAlignment(Qt.AlignCenter)

        self.title.setStyleSheet("""

            font-size:22px;

            font-weight:bold;

            padding:10px;

        """)

        layout.addWidget(self.title)

        # --------------------------------------------

        self.model = SelectionModel()

        self.view = QListView()

        self.view.setModel(self.model)

        self.view.setItemDelegate(
            SelectionDelegate()
        )

        self.view.doubleClicked.connect(
            self.item_selected
        )

        self.view.setSelectionMode(
            QListView.SingleSelection
        )

        self.view.setVerticalScrollMode(
            QListView.ScrollPerPixel
        )

        self.view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.view.setStyleSheet("""

        QListView{

            background:transparent;

            border:none;

            outline:none;

        }

        """)

        layout.addWidget(self.view)

        # --------------------------------------------

        self.footer = QLabel()

        self.footer.setAlignment(Qt.AlignCenter)

        self.footer.setText("Voice • Keyboard • Mouse")

        layout.addWidget(self.footer)

        # --------------------------------------------

        close = QPushButton("Close")

        close.clicked.connect(
            self.hide_overlay
        )

        layout.addWidget(close)

    # ======================================================

    def show_results(
        self,
        items,
        callback=None,
        title="NOVA"
    ):
        
        print("show_results() called")

        self.callback = callback

        self.title.setText(title)

        self.model.set_items(items)

        if self.model.rowCount():

            self.view.setCurrentIndex(
                self.model.index(0)
            )

        print("Calling show_overlay()")

        self.show_overlay()

    # ======================================================

    def item_selected(
        self,
        index
    ):

        if self.callback:

            self.callback(
                index.row()
            )

        self.hide_overlay()

    # ======================================================

    def keyPressEvent(
        self,
        event
    ):

        key = event.key()

        if key == Qt.Key_Escape:

            self.hide_overlay()

            return

        if key in (

            Qt.Key_Return,

            Qt.Key_Enter

        ):

            index = self.view.currentIndex()

            if index.isValid():

                self.item_selected(index)

                return

        super().keyPressEvent(event)

    # ======================================================

    def set_status(
        self,
        text
    ):

        self.footer.setText(text)

    # ======================================================

    def set_title(
        self,
        text
    ):

        self.title.setText(text)