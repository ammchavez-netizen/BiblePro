"""The pop-out chat window docks to the right of BibleQ-AI (or left / same screen if no room)."""
from PySide6.QtCore import QRect

import digital_bible.qml_ui.ai_controller as mod


class FakeScreen:
    def __init__(self, rect):
        self.rect = rect

    def availableGeometry(self):
        return self.rect


class FakeApp:
    _screens = []

    @classmethod
    def screens(cls):
        return cls._screens

    @classmethod
    def primaryScreen(cls):
        return cls._screens[0]


class FakeWin:
    """Window with Windows-like frame: 8px invisible borders + 31px title bar."""
    def __init__(self, x, y, w, h, shown=True, screen=None):
        self.g = QRect(x, y, w, h)
        self.shown = shown
        self._screen = screen

    def geometry(self):
        return QRect(self.g)

    def frameGeometry(self):
        if not self.shown:
            return QRect(self.g)
        return QRect(self.g.x() - 8, self.g.y() - 31, self.g.width() + 16, self.g.height() + 39)

    def setGeometry(self, x, y, w, h):
        self.g = QRect(x, y, w, h)

    def screen(self):
        return self._screen


def dock(main, chat, screens, monkeypatch):
    FakeApp._screens = screens
    monkeypatch.setattr(mod, "QGuiApplication", FakeApp)
    mod.AiController.dockWindow(None, chat, main)
    return chat


def test_docks_right_same_size(monkeypatch):
    left, right = FakeScreen(QRect(0, 0, 1920, 1040)), FakeScreen(QRect(1920, 0, 1920, 1040))
    main = FakeWin(100, 100, 1240, 820)
    chat = dock(main, FakeWin(0, 0, 500, 500), [left, right], monkeypatch)
    assert (chat.g.width(), chat.g.height()) == (1240, 820)
    assert chat.g.y() == main.g.y()
    # visible edges touch: main's visible right edge = chat's visible left edge (8px invisible borders)
    assert chat.frameGeometry().x() + 8 == main.frameGeometry().right() + 1 - 8


def test_falls_back_left_when_no_screen_on_right(monkeypatch):
    left, right = FakeScreen(QRect(0, 0, 1920, 1040)), FakeScreen(QRect(1920, 0, 1920, 1040))
    main = FakeWin(2500, 100, 1240, 820, screen=right)
    chat = dock(main, FakeWin(0, 0, 500, 500), [left, right], monkeypatch)
    assert chat.g.x() < main.g.x() and chat.g.width() == 1240


def test_single_screen_no_room_stays_on_screen(monkeypatch):
    only = FakeScreen(QRect(0, 0, 1920, 1040))
    main = FakeWin(0, 0, 1920, 1000, screen=only)
    chat = dock(main, FakeWin(0, 0, 500, 500, shown=False), [only], monkeypatch)
    assert 0 <= chat.frameGeometry().x() and chat.g.width() == 1920
