"""Details of the selected timeline event, in Manim terms (F02, MF.3).

Shows the call (``self.play(...)``/``self.wait(...)``), frames and seconds, and for
animations: class, category, ``run_time``, ``rate_func`` (with its curve), ``lag_ratio``,
the ``.animate`` chain and the target Mobject. Buttons jump to the event's start and
open its source line.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...catalog import CATEGORY_LABELS
from ..timeline_model import EventBox
from .theme import category_color, colors, is_dark


class RateCurveView(QWidget):
    """Plot of a rate function: t (0→1) across, progress up; dashed lines at 0 and 1."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Rate function curve")
        self.setMinimumSize(160, 90)
        self.curve: list[float] | None = None
        self.color = "#5b8fd6"

    def set_curve(self, curve: list[float] | None, color: str, name: str = "") -> None:
        self.curve, self.color = curve, color
        self.setAccessibleDescription(f"rate_func {name}" if name else "")
        self.setVisible(bool(curve))
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        if not self.curve:
            return
        app = QApplication.instance()
        c = colors(is_dark(app) if app else True)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        p.fillRect(QRectF(self.rect()), QColor(c["alt"]))
        lo, hi = min(0.0, *self.curve), max(1.0, *self.curve)
        span = (hi - lo) or 1.0

        def y(v: float) -> float:
            return r.bottom() - r.height() * (v - lo) / span

        p.setPen(QPen(QColor(c["muted"]), 1, Qt.PenStyle.DashLine))
        for v in (0.0, 1.0):
            p.drawLine(QPointF(r.left(), y(v)), QPointF(r.right(), y(v)))
        pts = [
            QPointF(r.left() + r.width() * i / (len(self.curve) - 1), y(v))
            for i, v in enumerate(self.curve)
        ]
        p.setPen(QPen(QColor(self.color), 2))
        p.drawPolyline(QPolygonF(pts))
        p.end()


class EventPanel(QWidget):
    seekRequested = Signal(int)
    sourceRequested = Signal(object)  # EventBox
    cueResetRequested = Signal(str)
    cueTimeRequested = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Event details")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self.title = QLabel("Select an event on the timeline.")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.details = QLabel("")
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.curve = RateCurveView()
        self.curve.setVisible(False)
        row = QHBoxLayout()
        self.go = QPushButton("Go to start")
        self.go.setAccessibleName("Move playhead to the event start")
        self.open = QPushButton("Open source")
        self.open.setAccessibleName("Open the event's source line in the code editor")
        row.addWidget(self.go)
        row.addWidget(self.open)
        self.cue_row = QWidget()
        crow = QHBoxLayout(self.cue_row)
        crow.setContentsMargins(0, 0, 0, 0)
        self.cue_time = QDoubleSpinBox()
        self.cue_time.setAccessibleName("Cue time in seconds")
        self.cue_time.setDecimals(3)
        self.cue_time.setSuffix(" s")
        self.cue_time.setRange(0, 86400)
        self.cue_set = QPushButton("Set time")
        self.cue_set.setAccessibleName("Move the cue to this time")
        self.cue_reset = QPushButton("Reset to default")
        self.cue_reset.setAccessibleName("Remove the cue's override")
        for w in (self.cue_time, self.cue_set, self.cue_reset):
            crow.addWidget(w)
        self.cue_row.setVisible(False)
        self.cue_set.clicked.connect(
            lambda: (
                self.box
                and self.cueTimeRequested.emit(self.box.meta["name"], self.cue_time.value())
            )
        )
        self.cue_reset.clicked.connect(
            lambda: self.box and self.cueResetRequested.emit(self.box.meta["name"])
        )
        lay.addWidget(self.title)
        lay.addWidget(self.details)
        lay.addWidget(self.curve)
        lay.addLayout(row)
        lay.addWidget(self.cue_row)
        lay.addStretch(1)
        self.box: EventBox | None = None
        self.fps = 15.0
        self.go.clicked.connect(lambda: self.box and self.seekRequested.emit(self.box.start))
        self.open.clicked.connect(lambda: self.box and self.sourceRequested.emit(self.box))
        self.show_event(None)

    def show_event(self, box: EventBox | None, fps: float | None = None) -> None:
        self.box = box
        if fps:
            self.fps = fps
        self.go.setEnabled(box is not None)
        is_cue = box is not None and box.kind == "cue"
        self.cue_row.setVisible(is_cue)
        if is_cue:
            self.cue_time.setValue(box.start / (fps or self.fps or 15.0))
            self.cue_reset.setEnabled(bool(box.meta.get("overridden")))
        self.open.setEnabled(bool(box and box.source))
        if box is None:
            self.title.setText("Select an event on the timeline.")
            self.details.setText("")
            self.curve.set_curve(None, "")
            return
        e = html.escape
        call = {
            "cue": "self.cue(…)",
            "play": "self.play(…)",
            "wait": "self.wait(…)",
            "section": "self.next_section(…)",
            "sound": "self.add_sound(…)",
            "animation": "animation in a group",
            "caption": "subcaption",
        }.get(box.kind, box.kind)
        self.title.setText(f"<b>{e(box.label or box.kind)}</b><br><small>{e(call)}</small>")
        fps = self.fps or 15.0
        rows: list[tuple[str, str]] = []
        if box.is_marker:
            rows.append(("Frame", f"{box.start} ({box.start / fps:.2f} s)"))
        else:
            rows.append(("Frames", f"{box.start}–{box.end - 1} ({box.end - box.start})"))
            rows.append(("Time", f"{box.start / fps:.2f}–{box.end / fps:.2f} s"))
        anim = box.animation
        if anim:
            cat = anim.get("category", "")
            rows.append(("Animation", f"{anim.get('class')}"))
            rows.append(("Category", CATEGORY_LABELS.get(cat, cat)))
            rows.append(("run_time", f"{anim.get('run_time', 0):g} s"))
            if anim.get("rate_func"):
                builtin = " (manim.rate_functions)" if anim.get("rate_func_builtin") else ""
                rows.append(("rate_func", anim["rate_func"] + builtin))
            if anim.get("lag_ratio"):
                rows.append(("lag_ratio", f"{anim['lag_ratio']:g}"))
            if anim.get("methods"):
                rows.append((".animate", ".".join(f"{m}()" for m in anim["methods"])))
            if anim.get("mobject"):
                name = anim.get("mobject_name")
                rows.append(("Mobject", anim["mobject"] + (f" “{name}”" if name else "")))
            flags = [f for f in ("introducer", "remover") if anim.get(f)]
            if flags:
                rows.append(("Adds/removes", ", ".join(flags)))
        elif box.kind == "play":
            classes = [a.get("class", "?") for a in box.meta.get("animations", [])]
            rows.append(("Animations", ", ".join(classes)))
        if box.kind == "wait":
            rows.append(("Frozen frame", "yes" if box.meta.get("frozen") else "no (updaters run)"))
        if box.kind == "cue":
            m = box.meta
            rows.append(("Reached at", f"{m['call_frame'] / fps:.3f} s"))
            rows.append(("Default", f"{m['default_frame'] / fps:.3f} s"))
            rows.append(("Override", "yes (cues.json)" if m.get("overridden") else "no"))
            rows.append(("Waits", f"{m['wait_frames'] / fps:.3f} s"))
            if m.get("description"):
                rows.append(("Description", m["description"]))
        if box.kind == "section":
            rows.append(("Type", str(box.meta.get("type") or "default")))
            rows.append(("skip_animations", str(bool(box.meta.get("skip_animations")))))
        if box.kind == "sound" and box.meta.get("clip"):
            cs = box.meta.get("clip_settings", {})
            rows.append(("Audio clip", f"{box.meta['clip']} (audio workspace)"))
            rows.append(("Source", str(cs.get("file", ""))))
            trim_out = cs.get("trim_out")
            rows.append(
                (
                    "Trim",
                    f"{cs.get('trim_in', 0):g}–{'end' if trim_out is None else f'{trim_out:g}'} s",
                )
            )
            rows.append(("Gain", f"{cs.get('gain_db', 0):+g} dB"))
            rows.append(
                ("Fades", f"in {cs.get('fade_in', 0):g} s, out {cs.get('fade_out', 0):g} s")
            )
        elif box.kind == "sound":
            rows.append(("File", Path(str(box.meta.get("file", ""))).name))
            if box.meta.get("gain") is not None:
                rows.append(("Gain", f"{box.meta['gain']}"))
        if box.source:
            rows.append(("Source", f"{box.source.get('path')}:{box.source.get('line')}"))
        rows.append(("ID", box.id))
        self.details.setText(
            "<table cellspacing=2>"
            + "".join(f"<tr><td><i>{e(k)}</i>&nbsp;</td><td>{e(v)}</td></tr>" for k, v in rows)
            + "</table>"
        )
        color = category_color(box.category)
        self.curve.set_curve(
            anim.get("rate_curve") if anim else None,
            color,
            anim.get("rate_func", "") if anim else "",
        )
