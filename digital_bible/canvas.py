"""Draws a verse "slide": background, auto-fitted verse text, reference footer.

The same routine renders the big display window and the small live preview in
the control window, so what the operator sees is exactly what is projected.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPixmap


# ---------------------------------------------------------------------------
# Top-left label (reference + version name) layout.
# All values are in pixels on a 1080p screen; they scale with the window size.
# ---------------------------------------------------------------------------
LABEL_LEFT = 36            # space from the left edge of the screen
LABEL_TOP = 75             # space from the top edge of the screen
LABEL_LINE_GAP = 0         # extra space between the reference and the version name
LABEL_GAP_BELOW = 12       # space between the label and the verse text
REFERENCE_SIZE = 60        # text size of the reference, e.g. "GENESIS 1:1"
VERSION_SIZE = 35          # text size of the version name, e.g. "ANG DATING BIBLIA"


@dataclass
class Slide:
    text: str = ""
    reference: str = ""
    version: str = ""
    blank: bool = False
    note: str = ""          # shown small instead of text (e.g. "not in this version")


class Renderer:
    def __init__(self, backgrounds_dir: Path):
        self.backgrounds_dir = Path(backgrounds_dir)
        self._bg_src = {}       # path -> QPixmap
        self._bg_scaled = {}    # (path, w, h) -> QPixmap
        self._fit = {}          # cache of fitted pixel sizes

    # ---------------------------------------------------------------- helpers
    def background_path(self, style: dict) -> Path | None:
        name = style.get("background") or ""
        if not name:
            return None
        p = Path(name)
        if not p.is_absolute():
            p = self.backgrounds_dir / name
        return p if p.exists() else None

    def _cover(self, path: Path, w: int, h: int) -> QPixmap | None:
        key = (str(path), w, h)
        if key in self._bg_scaled:
            return self._bg_scaled[key]
        src = self._bg_src.get(str(path))
        if src is None:
            src = QPixmap(str(path))
            self._bg_src[str(path)] = src
        if src.isNull():
            return None
        pm = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if len(self._bg_scaled) > 16:
            self._bg_scaled.clear()
        self._bg_scaled[key] = pm
        return pm

    @staticmethod
    def _font(style: dict, px: float) -> QFont:
        f = QFont(style.get("font_family") or "Microsoft Sans Serif")
        f.setPixelSize(max(1, int(px)))
        f.setBold(bool(style.get("bold", True)))
        f.setStyleStrategy(QFont.PreferAntialias)
        return f

    def _fit_size(self, text: str, rect: QRectF, style: dict, flags: int, max_px: float, min_px: float) -> float:
        key = (text, int(rect.width()), int(rect.height()), style.get("font_family"),
               style.get("bold"), int(max_px), flags)
        if key in self._fit:
            return self._fit[key]
        lo, hi, best = min_px, max_px, min_px
        for _ in range(14):
            mid = (lo + hi) / 2
            fm = QFontMetricsF(self._font(style, mid))
            br = fm.boundingRect(rect, flags, text)
            if br.height() <= rect.height() and br.width() <= rect.width() + 0.5:
                best, lo = mid, mid
            else:
                hi = mid
            if hi - lo < 0.5:
                break
        if len(self._fit) > 512:
            self._fit.clear()
        self._fit[key] = best
        return best

    # ------------------------------------------------------------------- draw
    def paint(self, p: QPainter, rect: QRectF, slide: Slide, style: dict):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = rect.width(), rect.height()

        if slide.blank:
            p.fillRect(rect, Qt.black)
            p.restore()
            return

        # Background
        p.fillRect(rect, QColor(style.get("bg_color", "#000000")))
        if style.get("bg_mode", "image") == "image":
            path = self.background_path(style)
            pm = self._cover(path, int(w), int(h)) if path else None
            if pm is not None:
                x = rect.x() + (w - pm.width()) / 2
                y = rect.y() + (h - pm.height()) / 2
                p.drawPixmap(QPointF(x, y), pm)
                dim = int(style.get("dim", 35))
                if dim:
                    p.fillRect(rect, QColor(0, 0, 0, int(255 * dim / 100)))

        scale = h / 1080.0
        margin = w * float(style.get("margin", 6)) / 100.0
        left = LABEL_LEFT * scale
        shadow = style.get("shadow", True)

        # ---- top-left label: reference (white) + version name (yellow italic)
        header_bottom = rect.y()
        lines = []
        if style.get("show_reference", True) and slide.reference:
            f = self._font(style, max(8.0, REFERENCE_SIZE * scale))
            f.setBold(False)
            lines.append((slide.reference, f, QColor(style.get("text_color", "#FFFFFF"))))
        if style.get("show_version", True) and slide.version:
            f = QFont("Microsoft Sans Serif")
            f.setStyleHint(QFont.Serif)
            f.setPixelSize(max(7, int(VERSION_SIZE * scale)))
            f.setBold(True)
            f.setItalic(True)
            lines.append((slide.version, f, QColor(style.get("ref_color", "#FFD54A"))))
        y = rect.y() + LABEL_TOP * scale
        for text_, f, color in lines:
            fm = QFontMetricsF(f)
            lrect = QRectF(rect.x() + left, y, w - 2 * left, fm.height())
            label = fm.elidedText(text_, Qt.ElideRight, lrect.width())
            p.setFont(f)
            if shadow:
                p.setPen(QColor(0, 0, 0, 170))
                p.drawText(lrect.translated(1.5 * scale + 1, 1.5 * scale + 1), int(Qt.AlignLeft | Qt.AlignTop), label)
            p.setPen(color)
            p.drawText(lrect, int(Qt.AlignLeft | Qt.AlignTop), label)
            header_bottom = y + fm.height()
            y = header_bottom + LABEL_LINE_GAP * scale

        # ---- verse text, fitted into the area below the label
        top = max(rect.y() + margin * 0.6, header_bottom + LABEL_GAP_BELOW * scale)
        body = QRectF(rect.x() + margin, top, w - 2 * margin, rect.bottom() - margin * 0.6 - top)
        align = Qt.AlignLeft if style.get("align") == "left" else Qt.AlignHCenter
        flags = int(align | Qt.AlignVCenter | Qt.TextWordWrap)
        text = slide.text or slide.note
        if text and body.width() > 10 and body.height() > 10:
            max_px = max(8.0, float(style.get("max_size", 110)) * scale)
            if not slide.text:
                max_px = 48 * scale
            px = self._fit_size(text, body, style, flags, max_px, max(4.0, 8 * scale))
            p.setFont(self._font(style, px))
            if shadow:
                off = max(1.0, px * 0.06)
                p.setPen(QColor(0, 0, 0, 170))
                p.drawText(body.translated(off, off), flags, text)
            p.setPen(QColor(style.get("text_color", "#FFFFFF")))
            p.drawText(body, flags, text)
        p.restore()
