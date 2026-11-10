"""QML item that draws the live slide preview with the same Renderer as the display."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QRectF, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtQml import QmlElement
from PySide6.QtQuick import QQuickPaintedItem

QML_IMPORT_NAME = "BiblePro.Native"
QML_IMPORT_MAJOR_VERSION = 1


@QmlElement
class SlidePreview(QQuickPaintedItem):
    controllerChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctrl = None
        self.setAntialiasing(True)

    def _get_ctrl(self):
        return self._ctrl

    def _set_ctrl(self, ctrl):
        if ctrl is self._ctrl:
            return
        if self._ctrl is not None:
            try:
                self._ctrl.slideChanged.disconnect(self.update)
            except (RuntimeError, TypeError):
                pass
        self._ctrl = ctrl
        if ctrl is not None:
            ctrl.slideChanged.connect(self.update)
        self.controllerChanged.emit()
        self.update()

    controller = Property(QObject, _get_ctrl, _set_ctrl, notify=controllerChanged)

    def paint(self, p: QPainter):
        r = QRectF(0, 0, self.width(), self.height())
        if self._ctrl is None or r.width() < 2 or r.height() < 2:
            return
        aspect = self._ctrl.display_aspect()
        w = min(r.width(), r.height() * aspect)
        h = w / aspect
        target = QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h)
        self._ctrl.renderer.paint(p, target, self._ctrl.visible_slide(), self._ctrl.settings.style)
        p.setPen(QColor(0, 0, 0, 40))
        p.drawRect(target.adjusted(0, 0, -1, -1))
