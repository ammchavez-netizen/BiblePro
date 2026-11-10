"""The audience-facing verse window.

Unlike the old app it is a normal window: move it, resize it, put it on any
monitor, go fullscreen there (F11 / double-click) and come back, or keep it
borderless / always-on-top. Nothing but the verse is drawn on it.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence, QPainter
from PySide6.QtWidgets import QMenu, QWidget

from . import APP_NAME
from .canvas import Renderer, Slide

EDGE = 8  # px grab area for resizing a borderless window


class DisplayWindow(QWidget):
    next_requested = Signal()
    prev_requested = Signal()
    blank_toggled = Signal()
    typed = Signal(str)                 # letters typed here are sent to the control window
    state_changed = Signal()            # geometry / mode changed -> save settings
    focus_controls = Signal()

    def __init__(self, renderer: Renderer, style: dict, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(f"{APP_NAME} — Display")
        self.setMinimumSize(240, 135)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.renderer = renderer
        self.style_ = style
        self.slide = Slide()
        self._frameless = False
        self._on_top = False
        self._normal_geometry: QRect | None = None
        self.resize(960, 540)

    # ---------------------------------------------------------------- placement
    def ensure_on_screen(self):
        """If the saved position is off every screen (e.g. settings copied from a PC with
        more monitors), center the window on the main screen."""
        g = self.frameGeometry() if self.isVisible() else self.geometry()
        for scr in QGuiApplication.screens():
            visible = scr.availableGeometry().intersected(g)
            if visible.width() >= 120 and visible.height() >= 80:
                return
        prim = QGuiApplication.primaryScreen().availableGeometry()
        w, h = min(self.width(), prim.width() - 80), min(self.height(), prim.height() - 80)
        self.setGeometry(prim.x() + (prim.width() - w) // 2, prim.y() + (prim.height() - h) // 2, w, h)

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self.isFullScreen():
            self.ensure_on_screen()

    # ---------------------------------------------------------------- content
    def set_slide(self, slide: Slide):
        self.slide = slide
        self.update()

    def set_style(self, style: dict):
        self.style_ = style
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        self.renderer.paint(p, QRectF(self.rect()), self.slide, self.style_)
        p.end()

    # ------------------------------------------------------------ window mode
    @property
    def frameless(self) -> bool:
        return self._frameless

    @property
    def on_top(self) -> bool:
        return self._on_top

    def _apply_flags(self):
        geo = self.geometry()
        visible = self.isVisible()
        flags = Qt.Window
        if self._frameless:
            flags |= Qt.FramelessWindowHint
        if self._on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if visible:
            self.setGeometry(geo)
            self.show()
        self.state_changed.emit()

    def set_frameless(self, on: bool):
        if on != self._frameless:
            self._frameless = on
            if not self.isFullScreen():
                self._apply_flags()

    def set_on_top(self, on: bool):
        if on != self._on_top:
            self._on_top = on
            self._apply_flags()

    def screen_names(self) -> list[str]:
        return [s.name() for s in QGuiApplication.screens()]

    def current_screen_name(self) -> str:
        s = self.screen() or QGuiApplication.primaryScreen()
        return s.name() if s else ""

    def go_fullscreen(self, screen_name: str | None = None):
        screens = QGuiApplication.screens()
        target = next((s for s in screens if s.name() == screen_name), None) or self.screen()
        if not self.isFullScreen():
            self._normal_geometry = self.geometry()
        else:
            self.showNormal()
        if target is not None:
            if self.windowHandle():
                self.windowHandle().setScreen(target)
            g = target.geometry()
            self.setGeometry(g.x() + 40, g.y() + 40, min(960, g.width() - 80), min(540, g.height() - 80))
        self.show()
        self.showFullScreen()
        self.state_changed.emit()

    def leave_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if self._frameless:
                self._apply_flags()
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self.state_changed.emit()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self.go_fullscreen()

    def move_to_screen(self, screen_name: str):
        """Fullscreen on that monitor (the usual case for a projector)."""
        self.go_fullscreen(screen_name)

    def windowed_geometry(self) -> QRect:
        if self.isFullScreen() and self._normal_geometry is not None:
            return self._normal_geometry
        return self.geometry()

    # ------------------------------------------------------------------ input
    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown, Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.next_requested.emit()
        elif k in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp, Qt.Key_Backspace):
            self.prev_requested.emit()
        elif k == Qt.Key_F11 or (k == Qt.Key_F and not ev.modifiers()):
            self.toggle_fullscreen()
        elif k == Qt.Key_Escape:
            self.leave_fullscreen()
        elif k == Qt.Key_B and not ev.modifiers() or k == Qt.Key_Period:
            self.blank_toggled.emit()
        elif ev.text() and ev.text().isprintable() and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self.typed.emit(ev.text())     # start typing a reference from here
        else:
            super().keyPressEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.toggle_fullscreen()

    def _edges(self, pos: QPoint):
        if not self._frameless or self.isFullScreen():
            return Qt.Edges()
        e = Qt.Edges()
        r = self.rect()
        if pos.x() <= EDGE:
            e |= Qt.LeftEdge
        if pos.x() >= r.width() - EDGE:
            e |= Qt.RightEdge
        if pos.y() <= EDGE:
            e |= Qt.TopEdge
        if pos.y() >= r.height() - EDGE:
            e |= Qt.BottomEdge
        return e

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._frameless and not self.isFullScreen() and self.windowHandle():
            edges = self._edges(ev.position().toPoint())
            if edges:
                self.windowHandle().startSystemResize(edges)
            else:
                self.windowHandle().startSystemMove()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        e = self._edges(ev.position().toPoint())
        if e in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif e in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif e & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif e & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(ev)

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        fs = m.addAction("Exit fullscreen  (Esc)" if self.isFullScreen() else "Fullscreen  (F11)")
        fs.triggered.connect(self.toggle_fullscreen)
        sm = m.addMenu("Fullscreen on screen")
        for i, s in enumerate(QGuiApplication.screens(), 1):
            g = s.geometry()
            a = sm.addAction(f"{i}: {s.name()}  ({g.width()}×{g.height()})")
            a.triggered.connect(lambda _=False, n=s.name(): self.move_to_screen(n))
        m.addSeparator()
        top = m.addAction("Always on top")
        top.setCheckable(True)
        top.setChecked(self._on_top)
        top.toggled.connect(self.set_on_top)
        fl = m.addAction("Borderless window")
        fl.setCheckable(True)
        fl.setChecked(self._frameless)
        fl.toggled.connect(self.set_frameless)
        m.addSeparator()
        m.addAction("Next verse  (→)").triggered.connect(self.next_requested.emit)
        m.addAction("Previous verse  (←)").triggered.connect(self.prev_requested.emit)
        m.addAction("Blank screen  (B)").triggered.connect(self.blank_toggled.emit)
        m.addSeparator()
        m.addAction("Show controls").triggered.connect(self.focus_controls.emit)
        m.addAction("Hide display").triggered.connect(self.hide)
        m.exec(ev.globalPos())

    def moveEvent(self, ev):
        super().moveEvent(ev)
        self.state_changed.emit()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.state_changed.emit()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() == QEvent.WindowStateChange:
            self.state_changed.emit()
