"""Viewport: shows the cached frame Manim rendered for the playhead (spec F01).

It never draws scene content itself (spec §4: the editor is not a renderer). Zoom is
either "fit" (default) or a fixed factor; Ctrl+wheel zooms. A text overlay reports
state (rendering progress, buffering, errors) in words, not colour alone.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from .theme import colors, is_dark

ZOOMS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)


class PixmapCache:
    """Small LRU of decoded frames, so playback doesn't decode PNGs repeatedly."""

    def __init__(self, capacity: int = 240) -> None:
        self.capacity = capacity
        self._items: OrderedDict[str, QPixmap] = OrderedDict()

    def get(self, path: Path) -> QPixmap | None:
        key = str(path)
        pm = self._items.get(key)
        if pm is not None:
            self._items.move_to_end(key)
            return pm
        pm = QPixmap(key)
        if pm.isNull():
            return None
        self._items[key] = pm
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return pm

    def clear(self) -> None:
        self._items.clear()


class Viewport(QWidget):
    zoomChanged = Signal(object)  # None = fit, else factor

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Viewport")
        self.setAccessibleDescription("Rendered frame at the playhead")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 180)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.cache = PixmapCache()
        self._pixmap: QPixmap | None = None
        self.frame_size: tuple[int, int] = (854, 480)
        self.zoom: float | None = None  # None = fit
        self.overlay = ""
        self.overlay_is_error = False
        self.placeholder = "Open a scene to preview it."

    # -- content ----------------------------------------------------------------------

    def show_frame(self, path: Path | None) -> None:
        self._pixmap = self.cache.get(path) if path else None
        if self._pixmap is not None:
            self.frame_size = (self._pixmap.width(), self._pixmap.height())
        self.update()

    @property
    def has_frame(self) -> bool:
        return self._pixmap is not None

    def set_overlay(self, text: str, *, error: bool = False) -> None:
        if (text, error) != (self.overlay, self.overlay_is_error):
            self.overlay, self.overlay_is_error = text, error
            self.setAccessibleDescription(text or "Rendered frame at the playhead")
            self.update()

    # -- zoom -------------------------------------------------------------------------

    def fit(self) -> None:
        self.zoom = None
        self.zoomChanged.emit(None)
        self.update()

    def set_zoom(self, factor: float) -> None:
        self.zoom = max(ZOOMS[0], min(factor, ZOOMS[-1]))
        self.zoomChanged.emit(self.zoom)
        self.update()

    def current_scale(self) -> float:
        if self.zoom is not None:
            return self.zoom
        w, h = self.frame_size
        if w <= 0 or h <= 0:
            return 1.0
        return min(self.width() / w, self.height() / h)

    def zoom_in(self) -> None:
        s = self.current_scale()
        self.set_zoom(next((z for z in ZOOMS if z > s + 1e-6), ZOOMS[-1]))

    def zoom_out(self) -> None:
        s = self.current_scale()
        self.set_zoom(next((z for z in reversed(ZOOMS) if z < s - 1e-6), ZOOMS[0]))

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt API)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_in() if event.angleDelta().y() > 0 else self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # -- painting ---------------------------------------------------------------------

    def frame_rect(self) -> QRectF:
        s = self.current_scale()
        w, h = self.frame_size[0] * s, self.frame_size[1] * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, event: object) -> None:  # noqa: N802 (Qt API)
        app = QApplication.instance()
        c = colors(is_dark(app) if app else True)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(c["viewport"]))
        rect = self.frame_rect()
        if self._pixmap is not None:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.current_scale() < 1)
            p.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
        else:
            p.fillRect(rect, QColor(c["alt"]))
            p.setPen(QColor(c["muted"]))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.placeholder)
        if self.overlay:
            self._paint_overlay(p, c)
        p.end()

    def _paint_overlay(self, p: QPainter, c: dict[str, str]) -> None:
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * 1.05)
        p.setFont(font)
        fm = p.fontMetrics()
        text = ("⚠ " if self.overlay_is_error else "") + self.overlay
        maxw = max(self.width() - 24, 50)
        br = fm.boundingRect(0, 0, maxw, 1000, Qt.TextFlag.TextWordWrap, text)
        box = QRectF(QPointF(12, 12), br.size().toSizeF()).adjusted(-8, -6, 8, 6)
        box.moveTopLeft(QPointF(12, 12))
        bg = QColor(c["base"])
        bg.setAlpha(225)
        p.fillRect(box, bg)
        p.setPen(QColor(c["error"] if self.overlay_is_error else c["text"]))
        p.drawText(box.adjusted(8, 6, -8, -6), Qt.TextFlag.TextWordWrap, text)
