from PySide6.QtCore import (
    Qt,
    QAbstractListModel,
    QModelIndex,
)


class SelectionModel(QAbstractListModel):

    def __init__(self, items=None):

        super().__init__()

        self.items = items or []

    # ======================================================

    def rowCount(self, parent=QModelIndex()):

        return len(self.items)

    # ======================================================

    def data(self, index, role):

        if not index.isValid():
            return None

        item = self.items[index.row()]

        if role == Qt.DisplayRole:
            return item

        return None

    # ======================================================

    def set_items(self, items):

        self.beginResetModel()

        self.items = items

        self.endResetModel()

    # ======================================================

    def get_item(self, row):

        if row < 0:
            return None

        if row >= len(self.items):
            return None

        return self.items[row]