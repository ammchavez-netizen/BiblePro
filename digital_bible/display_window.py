"""The audience-facing verse window.

Unlike the old app it is a normal window: move it, resize it, put it on any
monitor, go fullscreen there (F11 / double-click) and come back, or keep it
borderless / always-on-top. Nothing but the verse is drawn on it.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QMenu, QWidget

from . import APP_NAME
from .canvas import Renderer, Slide

EDGE = 14  # px grab area at each corner for resizing a borderless window

# Windows messages/hit-test codes used to allow resizing from the 4 corners only,
# and to keep the window's shape (width and height grow and shrink together)
WM_NCHITTEST, WM_SIZING, WM_ENTERSIZEMOVE = 0x0084, 0x0214, 0x0231
HTLEFT, HTRIGHT, HTTOP, HTBOTTOM, HTBORDER = 10, 11, 12, 15, 18
_SIDE_SIZING = {1, 2, 3, 6}            # WM_SIZING: left, right, top, bottom (not a corner)
WMSZ_LEFT_SIDE = {1, 4, 7}             # corners whose left edge moves (left, top-left, bottom-left)
WMSZ_TOP_SIDE = {3, 4, 5}              # corners whose top edge moves (top, top-left, top-right)


def keep_shape(w: float, h: float, aspect: float, min_w: float, min_h: float) -> tuple[int, int]:
    """Size (w, h) changed to the shape `aspect` (= width / height): follows whichever of the two
    the mouse moved more, and never goes below the minimum size."""
    if h * aspect >= w:
        w = h * aspect
    else:
        h = w / aspect
    k = max(1.0, min_w / w, min_h / h)
    return round(w * k), round(h * k)


class DisplayWindow(QWidget):
    next_requested = Signal()
    prev_requested = Signal()
    blank_toggled = Signal()
    typed = Signal(str)                 # letters typed here are sent to the control window
    state_changed = Signal()            # geometry / mode changed -> save settings
    focus_controls = Signal()
    reset_size_requested = Signal()

    def __init__(self, renderer: Renderer, style: dict, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(f"{APP_NAME} — Display")
        self.setMinimumSize(240, 135)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.renderer = renderer
        self.style_ = style
        self.slide = Slide()
        self._frameless = True              # the verse window never has a title bar or border
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self._on_top = False
        self._normal_geometry: QRect | None = None
        self._sizing = None                # (aspect, frame_w, frame_h) while a corner is dragged
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

    def reset_size(self, img_w: int, img_h: int) -> str:
        """Make the window a quarter of the screen (half its width and half its height),
        in the shape of the background image. Returns a short description."""
        if self.isFullScreen():
            self.leave_fullscreen()
        elif self.isMaximized():
            self.showNormal()
        scr = self.screen() or QGuiApplication.primaryScreen()
        sg, avail = scr.geometry(), scr.availableGeometry()
        box_w, box_h = sg.width() / 2, sg.height() / 2          # a quarter of the screen
        k = min(box_w / img_w, box_h / img_h)                   # image shape, as big as fits the quarter
        nw, nh = max(240, round(img_w * k)), max(135, round(img_h * k))
        fg, g = self.frameGeometry(), self.geometry()
        fw, fh = max(0, fg.width() - g.width()), max(0, fg.height() - g.height())
        # keep it where it is, but fully on the screen (borders and title bar included)
        left, top = g.x() - fg.x(), g.y() - fg.y()
        right, bottom = fw - left, fh - top
        x = min(max(g.x(), avail.x() + left), avail.x() + avail.width() - right - nw)
        y = min(max(g.y(), avail.y() + top), avail.y() + avail.height() - bottom - nh)
        self.setGeometry(int(x), int(y), nw, nh)
        self.state_changed.emit()
        return (f"Verse window set to a quarter of the screen ({nw}×{nh}), "
                f"in the shape of the background image ({img_w}×{img_h}).")

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
        h = Qt.Edges()
        v = Qt.Edges()
        r = self.rect()
        if pos.x() <= EDGE:
            h = Qt.LeftEdge
        elif pos.x() >= r.width() - EDGE:
            h = Qt.RightEdge
        if pos.y() <= EDGE:
            v = Qt.TopEdge
        elif pos.y() >= r.height() - EDGE:
            v = Qt.BottomEdge
        if not h or not v:              # only the 4 corners resize (not the sides)
            return Qt.Edges()
        return h | v

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
        m.addAction("Reset size (quarter of the screen)").triggered.connect(self.reset_size_requested.emit)
        m.addSeparator()
        m.addAction("Next verse  (→)").triggered.connect(self.next_requested.emit)
        m.addAction("Previous verse  (←)").triggered.connect(self.prev_requested.emit)
        m.addAction("Blank screen  (B)").triggered.connect(self.blank_toggled.emit)
        m.addSeparator()
        m.addAction("Show controls").triggered.connect(self.focus_controls.emit)
        m.addAction("Hide display").triggered.connect(self.hide)
        m.exec(ev.globalPos())

    def nativeEvent(self, event_type, message):
        """Windows: the sides don't resize, only the 4 corners, and a corner drag keeps the
        window's shape - width and height change together (diagonal resizing only)."""
        if sys.platform == "win32" and not self.isFullScreen():
            try:
                import ctypes
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                user32 = ctypes.windll.user32
                if msg.message == WM_NCHITTEST and not self._frameless:
                    user32.DefWindowProcW.restype = ctypes.c_ssize_t
                    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                    hit = user32.DefWindowProcW(msg.hWnd, msg.message, msg.wParam, msg.lParam)
                    if hit in (HTLEFT, HTRIGHT, HTTOP, HTBOTTOM):
                        return True, HTBORDER          # a side: no resize cursor, no resizing
                    return True, int(hit)
                if msg.message == WM_ENTERSIZEMOVE:
                    # remember the shape (client area) and the border size when a drag starts
                    cr, wr = wintypes.RECT(), wintypes.RECT()
                    user32.GetClientRect(msg.hWnd, ctypes.byref(cr))
                    user32.GetWindowRect(msg.hWnd, ctypes.byref(wr))
                    cw, ch = cr.right - cr.left, cr.bottom - cr.top
                    if cw > 0 and ch > 0:
                        self._sizing = (cw / ch, (wr.right - wr.left) - cw, (wr.bottom - wr.top) - ch)
                if msg.message == WM_SIZING:
                    r = wintypes.RECT.from_address(int(msg.lParam))
                    side = int(msg.wParam)
                    if side in _SIDE_SIZING or self._sizing is None:
                        # (e.g. keyboard sizing from the window menu) keep the current size
                        cur = wintypes.RECT()
                        user32.GetWindowRect(msg.hWnd, ctypes.byref(cur))
                        r.left, r.top, r.right, r.bottom = cur.left, cur.top, cur.right, cur.bottom
                        return True, 1
                    aspect, fw, fh = self._sizing
                    dpr = self.devicePixelRatioF() or 1.0
                    w, h = keep_shape(r.right - r.left - fw, r.bottom - r.top - fh, aspect,
                                      self.minimumWidth() * dpr, self.minimumHeight() * dpr)
                    W, H = w + fw, h + fh
                    if side in WMSZ_LEFT_SIDE:
                        r.left = r.right - W
                    else:
                        r.right = r.left + W
                    if side in WMSZ_TOP_SIDE:
                        r.top = r.bottom - H
                    else:
                        r.bottom = r.top + H
                    return True, 1
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

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
