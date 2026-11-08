"""Version selection: a type-to-filter popup grouped by language, plus favorites."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .library import Library, fold

STAR_ON, STAR_OFF = "★", "☆"


class VersionPicker(QDialog):
    """Popup list of all versions. Type to filter; Enter picks; click ☆ to favorite."""
    chosen = Signal(str)
    favorites_changed = Signal(list)

    def __init__(self, library: Library, current: str, favorites: list, parent=None):
        super().__init__(parent, Qt.Popup)
        self.library = library
        self.current = current
        self.favorites = list(favorites)
        self.resize(620, 520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.filter = QLineEdit(placeholderText="Filter by name, abbreviation or language…  (e.g. tagalog, kjv, reina)")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._populate)
        self.filter.installEventFilter(self)
        lay.addWidget(self.filter)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["", "Abbr", "Version", ""])
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(10)
        self.tree.setUniformRowHeights(True)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.resizeSection(0, 28)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.itemActivated.connect(self._activate)
        self.tree.itemClicked.connect(self._clicked)
        lay.addWidget(self.tree)
        lay.addWidget(QLabel("Enter / double-click to use  •  click ☆ to add to favorites (Ctrl+1…9)"))
        self._populate()

    def eventFilter(self, obj, ev):
        if obj is self.filter and ev.type() == QEvent.KeyPress:
            if ev.key() in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp):
                self.tree.setFocus()
                self.tree.keyPressEvent(ev)
                return True
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                item = self.tree.currentItem()
                if item and item.data(0, Qt.UserRole):
                    self._activate(item)
                return True
        return super().eventFilter(obj, ev)

    def _version_item(self, v) -> QTreeWidgetItem:
        it = QTreeWidgetItem(["", v.abbr, v.name.title() if v.name.isupper() else v.name, v.coverage])
        it.setText(0, STAR_ON if v.code in self.favorites else STAR_OFF)
        it.setData(0, Qt.UserRole, v.code)
        it.setToolTip(2, f"{v.name}\n{v.language} • {v.verse_count:,} verses\n{v.info}")
        if v.code == self.current:
            f = it.font(2)
            f.setBold(True)
            for c in range(4):
                it.setFont(c, f)
        return it

    def _group(self, title: str) -> QTreeWidgetItem:
        g = QTreeWidgetItem([title])
        g.setFirstColumnSpanned(True)
        f = QFont(g.font(0))
        f.setBold(True)
        g.setFont(0, f)
        g.setFlags(Qt.ItemIsEnabled)
        return g

    def _populate(self):
        q = fold(self.filter.text().strip())
        self.tree.clear()
        first = current_item = None

        def match(v):
            return not q or all(t in fold(f"{v.abbr} {v.name} {v.language} {v.coverage}") for t in q.split())

        groups = []
        favs = [self.library.by_code[c] for c in self.favorites if c in self.library.by_code]
        favs = [v for v in favs if match(v)]
        if favs:
            groups.append(("★ Favorites", favs))
        for lang in self.library.languages():
            vs = [v for v in self.library.versions if v.language == lang and match(v)]
            if vs:
                groups.append((lang, vs))
        for title, vs in groups:
            g = self._group(f"{title}  ({len(vs)})")
            self.tree.addTopLevelItem(g)
            for v in vs:
                it = self._version_item(v)
                g.addChild(it)
                first = first or it
                if v.code == self.current and current_item is None:
                    current_item = it
            g.setExpanded(True)
            g.setFirstColumnSpanned(True)
        target = first if q else (current_item or first)
        if target:
            self.tree.setCurrentItem(target)
            self.tree.scrollToItem(target)

    def _clicked(self, item, column):
        code = item.data(0, Qt.UserRole)
        if code and column == 0:
            if code in self.favorites:
                self.favorites.remove(code)
            else:
                self.favorites.append(code)
            self.favorites_changed.emit(list(self.favorites))
            self._populate()

    def _activate(self, item, _col=0):
        code = item.data(0, Qt.UserRole)
        if code:
            self.chosen.emit(code)
            self.accept()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.filter.setFocus()


class FavoritesBar(QWidget):
    """One-click buttons for favorite versions."""
    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self.buttons = {}

    def set_favorites(self, library: Library, favorites: list, current: str):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.buttons = {}
        for i, code in enumerate(c for c in favorites if c in library.by_code):
            v = library.by_code[code]
            b = QToolButton(text=v.abbr)
            b.setCheckable(True)
            b.setChecked(code == current)
            tip = v.name + (f"   (Ctrl+{i + 1})" if i < 9 else "")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, c=code: self.chosen.emit(c))
            self.lay.addWidget(b)
            self.buttons[code] = b
        self.lay.addStretch(1)

    def mark_current(self, current: str):
        for code, b in self.buttons.items():
            b.setChecked(code == current)
