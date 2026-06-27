from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect


class FadeAnimation:

    def __init__(self, widget):

        self.widget = widget

        self.effect = QGraphicsOpacityEffect(widget)

        widget.setGraphicsEffect(self.effect)

        self.animation = None

    # ==================================================

    def fade_in(self, duration=180):

        self.animation = QPropertyAnimation(
            self.effect,
            b"opacity"
        )

        self.animation.setDuration(duration)

        self.animation.setStartValue(0)

        self.animation.setEndValue(1)

        self.animation.setEasingCurve(
            QEasingCurve.OutCubic
        )

        self.widget.show()

        self.animation.start()

    # ==================================================

    def fade_out(self, duration=180):

        self.animation = QPropertyAnimation(
            self.effect,
            b"opacity"
        )

        self.animation.setDuration(duration)

        self.animation.setStartValue(1)

        self.animation.setEndValue(0)

        self.animation.setEasingCurve(
            QEasingCurve.InCubic
        )

        self.animation.finished.connect(
            self.widget.hide
        )

        self.animation.start()