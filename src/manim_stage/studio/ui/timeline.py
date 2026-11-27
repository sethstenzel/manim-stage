"""Timeline: ruler, lanes of play/wait/animation/section/sound events, playhead (F02, MF.3).

Manim-aware drawing (ADR-0011/0013):

- bars are coloured *and labelled* by Manim animation category (creation, fading, …);
- each bar wide enough shows its ``rate_func`` curve, sampled by the runner, so custom
  rate functions are drawn faithfully;
- ``LaggedStart``/``AnimationGroup`` members appear on nested level lanes, so lag
  ratios read as a staircase;
- waits are hatched (frozen waits say so), sections are flags with their name
  (``skip_animations`` sections say "skipped"), sounds sit on the Audio lane.

Mouse: click the ruler or empty space to seek (drag to scrub); click a bar to select;
double-click a bar to open its source line. Ctrl+wheel zooms around the cursor;
Shift+wheel or a horizontal wheel scrolls. Keyboard (when focused): Alt+←/→ previous/
next event, Enter go to selected event, Ctrl+Enter open source, +/− zoom, F fit.
"""

from __future__ import annotations

from collections.abc import Container
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QScrollBar,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...catalog import CATEGORY_LABELS
from ..timeline_model import EventBox, Layout, build_layout, ruler_ticks
from .theme import category_color, colors, is_dark

LABEL_W = 92
RULER_H = 24
STRIP_H = 4


def _c() -> dict[str, str]:
    app = QApplication.instance()
    return colors(is_dark(app) if app else True)


def describe(box: EventBox, fps: float) -> str:
    """Plain-text summary used for tooltips and accessibility."""
    secs = f"{box.start / fps:.2f}–{box.end / fps:.2f} s" if fps else ""
    frames = (
        f"frame {box.start}"
        if box.is_marker
        else f"frames {box.start}–{box.end - 1} ({box.end - box.start})"
    )
    lines = [f"{box.kind}: {box.label}", f"{frames} · {secs}"]
    anim = box.animation
    if anim:
        cat = CATEGORY_LABELS.get(anim.get("category", ""), anim.get("category", ""))
        bits = [f"{anim.get('class')} ({cat})", f"run_time {anim.get('run_time', 0):g} s"]
        if anim.get("rate_func"):
            bits.append(f"rate_func {anim['rate_func']}")
        if anim.get("lag_ratio"):
            bits.append(f"lag_ratio {anim['lag_ratio']:g}")
        lines.append(" · ".join(bits))
        if anim.get("methods"):
            lines.append(".animate." + "().".join(anim["methods"]) + "()")
        if anim.get("mobject"):
            name = anim.get("mobject_name")
            lines.append(f"Mobject: {anim['mobject']}" + (f" “{name}”" if name else ""))
    if box.kind == "wait" and box.meta.get("frozen"):
        lines.append("frozen frame (no updaters)")
    if box.kind == "section":
        if box.meta.get("skip_animations"):
            lines.append("skip_animations=True (not rendered)")
    if box.kind == "sound" and box.meta.get("gain") is not None:
        lines.append(f"gain {box.meta['gain']}")
    if box.source:
        lines.append(f"{box.source.get('path')}:{box.source.get('line')}")
    return "\n".join(lines)


class TimelineCanvas(QWidget):
    seekRequested = Signal(int)
    eventSelected = Signal(object)  # EventBox | None
    sourceRequested = Signal(object)  # EventBox
    viewChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Timeline")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.layout_: Layout | None = None
        self.ppf = 4.0  # pixels per frame
        self.scroll = 0.0  # first visible frame
        self.fit_mode = True
        self.playhead = 0
        self.cached: Container[int] = ()
        self.range: tuple[int, int] | None = None
        self.selected: str | None = None
        self.hover: str | None = None
        self._drag_seek = False
        fm = QFontMetrics(self.font())
        self.row_h = max(22, fm.height() + 8)

    # -- data -------------------------------------------------------------------------

    def set_timeline(self, timeline: dict[str, Any]) -> None:
        self.layout_ = build_layout(timeline)
        if self.selected and self.selected not in self.layout_.by_id:
            self.selected = None  # stable IDs: kept across re-renders when possible
            self.eventSelected.emit(None)
        self.setMinimumHeight(self.content_height())
        if self.fit_mode:
            self.fit()
        self.update()

    def content_height(self) -> int:
        rows = self.layout_.row_count if self.layout_ else 2
        return RULER_H + STRIP_H + rows * self.row_h + 4

    @property
    def total(self) -> int:
        return self.layout_.total if self.layout_ else 0

    @property
    def fps(self) -> float:
        return self.layout_.fps if self.layout_ else 15.0

    # -- geometry ---------------------------------------------------------------------

    def track_width(self) -> float:
        return max(self.width() - LABEL_W - 8, 10)

    def x_of(self, frame: float) -> float:
        return LABEL_W + (frame - self.scroll) * self.ppf

    def frame_of(self, x: float) -> int:
        f = int((x - LABEL_W) / self.ppf + self.scroll)
        return max(0, min(f, max(self.total - 1, 0)))

    def visible_frames(self) -> float:
        return self.track_width() / self.ppf

    def fit(self) -> None:
        self.fit_mode = True
        self.ppf = self.track_width() / max(self.total, 1)
        self.scroll = 0.0
        self.viewChanged.emit()
        self.update()

    def zoom(self, factor: float, around_x: float | None = None) -> None:
        anchor_x = around_x if around_x is not None else self.x_of(self.playhead)
        anchor_f = (anchor_x - LABEL_W) / self.ppf + self.scroll
        fit_ppf = self.track_width() / max(self.total, 1)
        self.ppf = max(fit_ppf, min(self.ppf * factor, 80.0))
        self.fit_mode = abs(self.ppf - fit_ppf) < 1e-9
        self.scroll = anchor_f - (anchor_x - LABEL_W) / self.ppf
        self.clamp_scroll()
        self.viewChanged.emit()
        self.update()

    def clamp_scroll(self) -> None:
        self.scroll = max(0.0, min(self.scroll, max(self.total - self.visible_frames(), 0.0)))

    def ensure_visible(self, frame: int) -> None:
        if self.fit_mode:
            return
        vis = self.visible_frames()
        if frame < self.scroll or frame >= self.scroll + vis:
            self.scroll = frame - vis * 0.1
            self.clamp_scroll()
            self.viewChanged.emit()

    def resizeEvent(self, e: Any) -> None:  # noqa: N802
        if self.fit_mode:
            self.ppf = self.track_width() / max(self.total, 1)
        self.clamp_scroll()
        super().resizeEvent(e)

    def box_rects(self) -> list[tuple[EventBox, QRectF, str]]:
        """(event, rect, lane key) for every event, in paint order."""
        out = []
        if not self.layout_:
            return out
        y = RULER_H + STRIP_H
        for lane in self.layout_.lanes:
            for row in lane.rows or [[]]:
                for box in row:
                    x0 = self.x_of(box.start)
                    if box.is_marker:
                        rect = QRectF(x0 - 5, y + 2, 10, self.row_h - 4)
                    else:
                        x1 = self.x_of(box.end)
                        rect = QRectF(x0, y + 3, max(x1 - x0, 2.0), self.row_h - 6)
                    out.append((box, rect, lane.key))
                y += self.row_h
        return out

    def box_at(self, pos: QPointF) -> EventBox | None:
        for box, rect, _ in reversed(self.box_rects()):
            hit = rect.adjusted(-2, 0, 2, 0) if box.is_marker else rect
            if hit.contains(pos):
                return box
        return None

    # -- painting ---------------------------------------------------------------------

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        c = _c()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(c["base"]))
        if not self.layout_:
            p.setPen(QColor(c["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No timeline yet.")
            p.end()
            return
        self._paint_lanes(p, c)
        p.setClipRect(QRectF(LABEL_W, 0, self.width() - LABEL_W, self.height()))
        self._paint_range(p, c)
        self._paint_ruler(p, c)
        self._paint_cached(p, c)
        self._paint_section_lines(p, c)
        for box, rect, _ in self.box_rects():
            if rect.right() < LABEL_W or rect.left() > self.width():
                continue
            self._paint_box(p, c, box, rect)
        self._paint_playhead(p, c)
        p.end()

    def _paint_lanes(self, p: QPainter, c: dict[str, str]) -> None:
        y = RULER_H + STRIP_H
        p.fillRect(QRectF(0, 0, LABEL_W, self.height()), QColor(c["alt"]))
        for i, lane in enumerate(self.layout_.lanes):
            h = max(1, len(lane.rows)) * self.row_h
            if i % 2:
                p.fillRect(QRectF(LABEL_W, y, self.width(), h), QColor(c["window"]))
            p.setPen(QColor(c["muted"]))
            p.drawText(
                QRectF(6, y, LABEL_W - 10, self.row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                lane.title,
            )
            p.setPen(QPen(QColor(c["uncached"]), 1))
            p.drawLine(QPointF(0, y + h), QPointF(self.width(), y + h))
            y += h

    def _paint_ruler(self, p: QPainter, c: dict[str, str]) -> None:
        p.fillRect(QRectF(LABEL_W, 0, self.width(), RULER_H), QColor(c["alt"]))
        first, last = self.scroll, self.scroll + self.visible_frames()
        for t in ruler_ticks(self.fps, self.ppf, first, last):
            x = self.x_of(t.frame)
            p.setPen(QPen(QColor(c["muted"] if t.major else c["uncached"]), 1))
            p.drawLine(QPointF(x, RULER_H - (10 if t.major else 5)), QPointF(x, RULER_H))
            if t.label:
                p.setPen(QColor(c["text"]))
                p.drawText(QPointF(x + 3, RULER_H - 10), t.label)

    def _paint_cached(self, p: QPainter, c: dict[str, str]) -> None:
        y = RULER_H
        p.fillRect(QRectF(LABEL_W, y, self.width(), STRIP_H), QColor(c["uncached"]))
        run = None
        lo, hi = int(self.scroll), int(self.scroll + self.visible_frames()) + 1
        for f in range(lo, min(hi, self.total) + 1):
            inside = f < self.total and f in self.cached
            if inside and run is None:
                run = f
            elif not inside and run is not None:
                p.fillRect(
                    QRectF(self.x_of(run), y, (f - run) * self.ppf, STRIP_H), QColor(c["cached"])
                )
                run = None

    def _paint_range(self, p: QPainter, c: dict[str, str]) -> None:
        if not self.range:
            return
        a, b = self.range
        col = QColor(c["highlight"])
        col.setAlpha(40)
        p.fillRect(QRectF(self.x_of(a), 0, (b - a) * self.ppf, self.height()), col)

    def _paint_section_lines(self, p: QPainter, c: dict[str, str]) -> None:
        col = QColor(category_color("section"))
        col.setAlpha(110)
        p.setPen(QPen(col, 1, Qt.PenStyle.DashLine))
        for box in self.layout_.by_id.values():
            if box.kind == "section":
                x = self.x_of(box.start)
                p.drawLine(QPointF(x, RULER_H), QPointF(x, self.height()))

    def _paint_box(self, p: QPainter, c: dict[str, str], box: EventBox, rect: QRectF) -> None:
        cat = box.category
        base = QColor(category_color(cat))
        selected, hovered = box.id == self.selected, box.id == self.hover
        if box.is_marker:
            path = QPainterPath()
            path.addPolygon(
                QPolygonF(
                    [
                        rect.topLeft(),
                        QPointF(rect.right() + 4, rect.top() + 5),
                        QPointF(rect.left(), rect.top() + 10),
                    ]
                )
            )
            p.fillPath(path, base)
            p.setPen(QPen(base, 2))
            p.drawLine(rect.topLeft(), rect.bottomLeft())
            label = box.label + (" (skipped)" if box.meta.get("skip_animations") else "")
            p.setPen(QColor(c["text"]))
            p.drawText(QPointF(rect.right() + 6, rect.center().y() + 4), label)
            if selected:
                p.setPen(QPen(QColor(c["highlight"]), 2))
                p.drawRect(rect.adjusted(-2, -1, 2, 1))
            return
        fill = QColor(base)
        fill.setAlpha(235 if hovered or selected else 200)
        p.setPen(QPen(base.darker(140), 1))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 3, 3)
        if cat == "wait":
            hatch = QBrush(QColor(c["muted"]), Qt.BrushStyle.BDiagPattern)
            p.fillRect(rect.adjusted(1, 1, -1, -1), hatch)
        anim = box.animation
        if anim and anim.get("rate_curve") and rect.width() > 24:
            self._paint_curve(p, rect, anim["rate_curve"])
        if rect.width() > 28:
            label = box.label
            if box.kind == "wait":
                label = "wait (frozen)" if box.meta.get("frozen") else "wait"
            fm = p.fontMetrics()
            text = fm.elidedText(label, Qt.TextElideMode.ElideRight, int(rect.width() - 8))
            p.setPen(QColor("#ffffff") if cat != "wait" else QColor(c["text"]))
            p.drawText(
                rect.adjusted(4, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
        if selected:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c["playhead"]), 2))
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 3, 3)

    def _paint_curve(self, p: QPainter, rect: QRectF, curve: list[float]) -> None:
        lo, hi = min(0.0, *curve), max(1.0, *curve)
        span = (hi - lo) or 1.0
        inner = rect.adjusted(2, 3, -2, -3)
        pts = [
            QPointF(
                inner.left() + inner.width() * i / (len(curve) - 1),
                inner.bottom() - inner.height() * (v - lo) / span,
            )
            for i, v in enumerate(curve)
        ]
        col = QColor("#ffffff")
        col.setAlpha(110)
        p.setPen(QPen(col, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF(pts))

    def _paint_playhead(self, p: QPainter, c: dict[str, str]) -> None:
        if self.total <= 0:
            return
        x = self.x_of(self.playhead + 0.5) if self.ppf > 6 else self.x_of(self.playhead)
        col = QColor(c["playhead"])
        p.setPen(QPen(col, 2))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(x - 6, 0), QPointF(x + 6, 0), QPointF(x, 8)]))

    # -- interaction ------------------------------------------------------------------

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton or e.position().x() < LABEL_W:
            return
        pos = e.position()
        box = None if pos.y() < RULER_H + STRIP_H else self.box_at(pos)
        if box is not None:
            self.select(box.id)
        else:
            self._drag_seek = True
            self.seekRequested.emit(self.frame_of(pos.x()))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        pos = e.position()
        if self._drag_seek and e.buttons() & Qt.MouseButton.LeftButton:
            self.seekRequested.emit(self.frame_of(pos.x()))
            return
        box = self.box_at(pos) if pos.x() >= LABEL_W else None
        hid = box.id if box else None
        if hid != self.hover:
            self.hover = hid
            self.update()
        if box:
            QToolTip.showText(e.globalPosition().toPoint(), describe(box, self.fps), self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self._drag_seek = False

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        box = self.box_at(e.position())
        if box is not None:
            self.sourceRequested.emit(box)

    def leaveEvent(self, e: Any) -> None:  # noqa: N802
        self.hover = None
        self.update()

    def wheelEvent(self, e: QWheelEvent) -> None:  # noqa: N802
        d = e.angleDelta()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if d.y() > 0 else 0.8, e.position().x())
            e.accept()
        elif e.modifiers() & Qt.KeyboardModifier.ShiftModifier or d.x():
            delta = d.x() or d.y()
            self.fit_mode = False
            self.scroll -= delta / 120 * self.visible_frames() * 0.1
            self.clamp_scroll()
            self.viewChanged.emit()
            self.update()
            e.accept()
        else:
            e.ignore()  # let the scroll area scroll lanes vertically

    def select(self, event_id: str | None) -> None:
        self.selected = event_id
        box = self.layout_.by_id.get(event_id) if (self.layout_ and event_id) else None
        self.setAccessibleDescription(describe(box, self.fps) if box else "")
        self.eventSelected.emit(box)
        self.update()

    def select_step(self, direction: int) -> None:
        if not self.layout_:
            return
        order = self.layout_.ordered()
        if not order:
            return
        ids = [b.id for b in order]
        if self.selected in ids:
            i = max(0, min(ids.index(self.selected) + direction, len(ids) - 1))
        else:
            i = next((k for k, b in enumerate(order) if b.start >= self.playhead), 0)
        self.select(ids[i])
        self.ensure_visible(order[i].start)

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        k, mods = e.key(), e.modifiers()
        alt = mods & Qt.KeyboardModifier.AltModifier
        ctrl = mods & Qt.KeyboardModifier.ControlModifier
        box = self.layout_.by_id.get(self.selected) if (self.layout_ and self.selected) else None
        if alt and k in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.select_step(-1 if k == Qt.Key.Key_Left else 1)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and box is not None:
            (self.sourceRequested if ctrl else self.seekRequested).emit(box if ctrl else box.start)
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom(1.25)
        elif k == Qt.Key.Key_Minus:
            self.zoom(0.8)
        elif k == Qt.Key.Key_F:
            self.fit()
        else:
            super().keyPressEvent(e)


class TimelineView(QWidget):
    """Canvas in a vertical scroll area, plus a horizontal scroll bar and zoom buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Timeline panel")
        self.canvas = TimelineCanvas()
        self.area = QScrollArea()
        self.area.setWidget(self.canvas)
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hbar = QScrollBar(Qt.Orientation.Horizontal)
        self.hbar.setAccessibleName("Timeline horizontal scroll")
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 4, 0)
        self.legend = QLabel("")
        self.legend.setAccessibleName("Timeline legend")
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        bar.addWidget(self.legend, 1)
        for text, name, slot in (
            ("−", "Zoom timeline out", lambda: self.canvas.zoom(0.8)),
            ("+", "Zoom timeline in", lambda: self.canvas.zoom(1.25)),
            ("Fit", "Fit timeline", self.canvas.fit),
        ):
            b = QToolButton()
            b.setText(text)
            b.setAccessibleName(name)
            b.setToolTip(name)
            b.clicked.connect(slot)
            bar.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(bar)
        lay.addWidget(self.area, 1)
        lay.addWidget(self.hbar)
        self.canvas.viewChanged.connect(self._sync_bar)
        self.hbar.valueChanged.connect(self._bar_moved)
        self._syncing = False

    def set_timeline(self, timeline: dict[str, Any]) -> None:
        self.canvas.set_timeline(timeline)
        self._update_legend()
        self._sync_bar()

    def _update_legend(self) -> None:
        lay = self.canvas.layout_
        if not lay:
            self.legend.setText("")
            return
        cats = sorted({b.category for b in lay.by_id.values()})
        chips = [
            f'<span style="color:{category_color(k)}">■</span> '
            f"{CATEGORY_LABELS.get(k, k.capitalize())}"
            for k in cats
        ]
        self.legend.setText("&nbsp;&nbsp;".join(chips))

    def _sync_bar(self) -> None:
        c = self.canvas
        self._syncing = True
        vis = int(c.visible_frames())
        self.hbar.setRange(0, max(c.total - vis, 0))
        self.hbar.setPageStep(max(vis, 1))
        self.hbar.setValue(int(c.scroll))
        self.hbar.setVisible(c.total > vis)
        self._syncing = False
        c.update()

    def _bar_moved(self, value: int) -> None:
        if self._syncing:
            return
        self.canvas.fit_mode = False
        self.canvas.scroll = float(value)
        self.canvas.update()

    def set_state(
        self, playhead: int, cached: Container[int], range_: tuple[int, int] | None
    ) -> None:
        c = self.canvas
        c.playhead, c.cached, c.range = playhead, cached, range_
        before = c.scroll
        c.ensure_visible(playhead)
        if c.scroll != before:
            self._sync_bar()
        c.update()
