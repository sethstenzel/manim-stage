"""Transport icons drawn with QPainter in the theme's text colour.

Our own simple geometric shapes (no third-party icon assets), so they stay legible
in both dark and light themes and scale with the display.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

SIZE = 64


def _tri(path: QPainterPath, x0: float, x1: float, pointing_right: bool = True) -> None:
    tip, base = (x1, x0) if pointing_right else (x0, x1)
    path.moveTo(base, 14)
    path.lineTo(tip, 32)
    path.lineTo(base, 50)
    path.closeSubpath()


SHAPES = {
    "play": lambda p: _tri(p, 20, 50),
    "pause": lambda p: (p.addRect(QRectF(18, 14, 10, 36)), p.addRect(QRectF(36, 14, 10, 36))),
    "prev": lambda p: (p.addRect(QRectF(16, 14, 6, 36)), _tri(p, 24, 48, False)),
    "next": lambda p: (_tri(p, 16, 40), p.addRect(QRectF(42, 14, 6, 36))),
    "start": lambda p: (
        p.addRect(QRectF(10, 14, 6, 36)),
        _tri(p, 16, 36, False),
        _tri(p, 34, 54, False),
    ),  # fmt: skip
    "end": lambda p: (_tri(p, 10, 30), _tri(p, 28, 48), p.addRect(QRectF(48, 14, 6, 36))),
}


def make_icon(name: str, color: str) -> QIcon:
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    if name == "loop":
        pen = QPen(c, 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(QRectF(14, 14, 36, 36), 30 * 16, 300 * 16)
        head = QPainterPath()
        head.moveTo(QPointF(50, 12))
        head.lineTo(QPointF(52, 30))
        head.lineTo(QPointF(36, 24))
        head.closeSubpath()
        p.fillPath(head, c)
    else:
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        SHAPES[name](path)
        p.fillPath(path, c)
    p.end()
    return QIcon(pm)
