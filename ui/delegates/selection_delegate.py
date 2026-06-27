from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyle,
)


class SelectionDelegate(QStyledItemDelegate):

    ROW_HEIGHT = 72

    def sizeHint(self, option, index):
        return QSize(
            option.rect.width(),
            self.ROW_HEIGHT
        )

    # ======================================================

    def paint(
        self,
        painter,
        option,
        index
    ):

        item = index.data(Qt.DisplayRole)

        if item is None:
            return

        painter.save()

        rect = option.rect.adjusted(
            8,
            4,
            -8,
            -4
        )

        # ------------------------------------
        # Background
        # ------------------------------------

        if option.state & QStyle.State_Selected:

            painter.setBrush(QColor("#2E7DFF"))
            painter.setPen(Qt.NoPen)

            painter.drawRoundedRect(
                rect,
                10,
                10
            )

            text_color = QColor("white")

        else:

            painter.setBrush(QColor("#242424"))
            painter.setPen(Qt.NoPen)

            painter.drawRoundedRect(
                rect,
                10,
                10
            )

            text_color = QColor("#F5F5F5")

        # ------------------------------------
        # Border
        # ------------------------------------

        painter.setPen(
            QPen(
                QColor("#444"),
                1
            )
        )

        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            rect,
            10,
            10
        )

        # ------------------------------------
        # File Name
        # ------------------------------------

        painter.setPen(text_color)

        font = QFont()
        font.setPointSize(11)
        font.setBold(True)

        painter.setFont(font)

        painter.drawText(

            QRect(
                rect.left() + 18,
                rect.top() + 10,
                rect.width() - 30,
                22
            ),

            Qt.AlignLeft,

            item.get("name", "Unknown")

        )

        # ------------------------------------
        # Path
        # ------------------------------------

        painter.setPen(QColor("#AAAAAA"))

        font.setBold(False)
        font.setPointSize(9)

        painter.setFont(font)

        painter.drawText(

            QRect(
                rect.left() + 18,
                rect.top() + 38,
                rect.width() - 30,
                18
            ),

            Qt.AlignLeft,

            item.get("path", "")

        )

        painter.restore()