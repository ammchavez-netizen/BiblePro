"""The AI Mode conversation as a Qt list model.

Each row is one message (a dict exposed to QML as the role `entry`). Updating a row
while Gemini is writing only refreshes that row, so the chat doesn't flicker, keeps
its scroll position, and expanded/collapsed sections stay as the user left them.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal

ENTRY_ROLE = Qt.UserRole + 1


class ChatModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

    # ---- Qt model API
    def roleNames(self):
        return {ENTRY_ROLE: b"entry"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=ENTRY_ROLE):
        if index.isValid() and 0 <= index.row() < len(self._items) and role == ENTRY_ROLE:
            return self._items[index.row()]
        return None

    # ---- Python API
    @property
    def items(self) -> list[dict]:
        return list(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, row):
        return self._items[row]

    def append(self, entry: dict) -> int:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(dict(entry))
        self.endInsertRows()
        self.countChanged.emit()
        return row

    def update(self, row: int, entry: dict, merge: bool = True):
        if not 0 <= row < len(self._items):
            return
        self._items[row] = {**self._items[row], **entry} if merge else dict(entry)
        ix = self.index(row, 0)
        self.dataChanged.emit(ix, ix, [ENTRY_ROLE])

    def clear(self):
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.countChanged.emit()
