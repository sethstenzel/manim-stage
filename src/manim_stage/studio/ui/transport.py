"""Transport bar: play/pause, step, speed, loop, timecode and a scrub bar (spec F01).

The scrub bar shows which frames are already rendered (filled) and the play range,
so "slow re-render" is visible (spec §9). Detailed event tracks live in the timeline.
"""

from __future__ import annotations

from collections.abc import Container

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QWidget,
)

from ..playback import SPEEDS
from .icons import make_icon
from .theme import colors, is_dark


class ScrubBar(QWidget):
    """Thin bar: cached frames, play range, playhead. Click or drag to seek."""

    seek = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Scrub bar")
        self.setMinimumHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.total = 0
        self.frame = 0
        self.cached: Container[int] = ()
        self.cached_count = 0
        self.range: tuple[int, int] | None = None

    def set_state(
        self,
        total: int,
        frame: int,
        cached: Container[int],
        cached_count: int,
        range_: tuple[int, int] | None,
    ) -> None:
        self.total, self.frame, self.cached = total, frame, cached
        self.cached_count, self.range = cached_count, range_
        self.setAccessibleDescription(
            f"Frame {frame + 1} of {total}; {cached_count} of {total} frames rendered"
        )
        self.update()

    def frame_at(self, x: float) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(int(x / max(self.width(), 1) * self.total), self.total - 1))

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self.seek.emit(self.frame_at(e.position().x()))

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self.seek.emit(self.frame_at(e.position().x()))

    def paintEvent(self, event: object) -> None:  # noqa: N802
        app = QApplication.instance()
        c = colors(is_dark(app) if app else True)
        p = QPainter(self)
        h, w = self.height(), self.width()
        bar = QRectF(0, h * 0.3, w, h * 0.4)
        p.fillRect(bar, QColor(c["uncached"]))
        if self.total > 0:
            px = w / self.total
            # merge runs of cached frames into rectangles
            run_start = None
            for i in range(self.total + 1):
                inside = i < self.total and i in self.cached
                if inside and run_start is None:
                    run_start = i
                elif not inside and run_start is not None:
                    p.fillRect(
                        QRectF(run_start * px, bar.top(), (i - run_start) * px, bar.height()),
                        QColor(c["cached"]),
                    )
                    run_start = None
            if self.range:
                a, b = self.range
                pen = QColor(c["text"])
                p.setPen(pen)
                p.drawLine(int(a * px), 0, int(a * px), h)
                p.drawLine(int(b * px) - 1, 0, int(b * px) - 1, h)
                p.drawLine(int(a * px), 1, int(b * px) - 1, 1)
            x = (self.frame + 0.5) * px
            p.fillRect(QRectF(x - 1.5, 0, 3, h), QColor(c["playhead"]))
        p.end()


def _button(icon: str, name: str, tip: str, *, checkable: bool = False) -> QToolButton:
    b = QToolButton()
    b.setProperty("icon_name", icon)
    b.setAccessibleName(name)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setAutoRaise(True)
    b.setMinimumWidth(32)
    return b


class TransportBar(QWidget):
    playToggled = Signal()
    stepRequested = Signal(int)
    jumpRequested = Signal(str)  # "start" | "end"
    speedChanged = Signal(float)
    loopToggled = Signal(bool)
    frameEntered = Signal(int)
    audioToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Playback controls")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        self.btn_start = _button("start", "Go to start", "Go to start (Home)")
        self.btn_back = _button("prev", "Previous frame", "Previous frame (Left; Shift+Left: 1 s)")
        self.btn_play = _button("play", "Play", "Play / pause (Space)")
        self.btn_fwd = _button("next", "Next frame", "Next frame (Right; Shift+Right: 1 s)")
        self.btn_end = _button("end", "Go to end", "Go to end (End)")
        self.btn_loop = _button("loop", "Loop", "Loop playback (L)", checkable=True)
        self.btn_loop.setChecked(True)
        self.btn_audio = _button(
            "audio", "Preview audio", "Play the scene's sound while previewing", checkable=True
        )
        self.btn_audio.setChecked(True)
        self.speed = QComboBox()
        self.speed.setAccessibleName("Playback speed")
        self.speed.setToolTip("Playback speed")
        for s in SPEEDS:
            self.speed.addItem(f"{s:g}×", s)
        self.speed.setCurrentIndex(SPEEDS.index(1.0))
        self.scrub = ScrubBar()
        self.timecode = QLabel("00:00.00")
        self.timecode.setAccessibleName("Timecode")
        self.timecode.setToolTip("Time (minutes:seconds.frame)")
        self.timecode.setMinimumWidth(80)
        self.frame_box = QSpinBox()
        self.frame_box.setAccessibleName("Frame number")
        self.frame_box.setToolTip("Frame index (type to jump)")
        self.frame_box.setRange(0, 0)
        self.frame_box.setKeyboardTracking(False)
        self.total_label = QLabel("/ 0")
        for w in (self.btn_start, self.btn_back, self.btn_play, self.btn_fwd, self.btn_end):
            lay.addWidget(w)
        lay.addWidget(self.scrub, 1)
        for w in (
            self.timecode,
            self.frame_box,
            self.total_label,
            self.speed,
            self.btn_loop,
            self.btn_audio,
        ):
            lay.addWidget(w)

        self.btn_play.clicked.connect(self.playToggled)
        self.btn_back.clicked.connect(lambda: self.stepRequested.emit(-1))
        self.btn_fwd.clicked.connect(lambda: self.stepRequested.emit(1))
        self.btn_start.clicked.connect(lambda: self.jumpRequested.emit("start"))
        self.btn_end.clicked.connect(lambda: self.jumpRequested.emit("end"))
        self.btn_loop.toggled.connect(self.loopToggled)
        self.btn_audio.toggled.connect(self.audioToggled)
        self.speed.currentIndexChanged.connect(
            lambda i: self.speedChanged.emit(float(self.speed.itemData(i)))
        )
        self.frame_box.valueChanged.connect(self._frame_typed)
        self._updating = False
        self.refresh_icons()

    def refresh_icons(self) -> None:
        """Redraw icons in the current theme's text colour (call after a theme change)."""
        app = QApplication.instance()
        color = colors(is_dark(app) if app else True)["text"]
        for b in self.findChildren(QToolButton):
            name = b.property("icon_name")
            if name and (b.property("icon_drawn") != (name, color)):
                b.setIcon(make_icon(name, color))
                b.setProperty("icon_drawn", (name, color))

    def set_audio_state(self, available: bool, reason: str = "") -> None:
        self.btn_audio.setEnabled(available)
        if not available:
            self.btn_audio.setChecked(False)
            self.btn_audio.setToolTip(f"Preview audio unavailable: {reason}")

    def audio_on(self) -> bool:
        return self.btn_audio.isChecked()

    def _frame_typed(self, value: int) -> None:
        if not self._updating:
            self.frameEntered.emit(value)

    def show_state(
        self, *, playing: bool, buffering: bool, frame: int, total: int, timecode: str
    ) -> None:
        self.btn_play.setProperty("icon_name", "pause" if playing else "play")
        self.refresh_icons()
        self.btn_play.setAccessibleName("Pause" if playing else "Play")
        self.timecode.setText(timecode + (" ⏳" if buffering else ""))
        self._updating = True
        self.frame_box.setRange(0, max(total - 1, 0))
        self.frame_box.setValue(frame)
        self._updating = False
        self.total_label.setText(f"/ {max(total - 1, 0)}")
