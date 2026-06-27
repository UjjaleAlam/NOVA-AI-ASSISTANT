from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsDropShadowEffect,
)

from ui.animations.fade import FadeAnimation


class NovaOverlay(QWidget):

    closed = Signal()

    WIDTH = 650
    HEIGHT = 450

    def __init__(self):
        super().__init__()

        self.setup_window()

        self.setup_shadow()

        self.fade = FadeAnimation(self)

    # ==================================================

    def setup_window(self):

        self.setWindowFlags(

            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint

        )

        self.setAttribute(
            Qt.WA_TranslucentBackground
        )

        self.resize(
            self.WIDTH,
            self.HEIGHT
        )

        self.hide()

    # ==================================================

    def setup_shadow(self):

        shadow = QGraphicsDropShadowEffect(self)

        shadow.setBlurRadius(40)

        shadow.setOffset(0)

        shadow.setColor(
            QColor(0, 0, 0, 180)
        )

        self.setGraphicsEffect(shadow)

    # ==================================================

    def center(self):

        screen = self.screen()

        if screen is None:
            return

        geometry = screen.availableGeometry()

        x = geometry.center().x() - self.width() // 2

        y = geometry.center().y() - self.height() // 2

        self.move(x, y)

    # ==================================================

    def show_overlay(self):

        self.center()

        self.raise_()

        self.activateWindow()

        self.fade.fade_in()

    # ==================================================

    def hide_overlay(self):

        self.fade.fade_out()

        self.closed.emit()