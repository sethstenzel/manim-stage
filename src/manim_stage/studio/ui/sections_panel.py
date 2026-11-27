"""Sections tab: Manim ``next_section`` navigator (backlog MF.7).

Lists the scene's sections (name, start, length, type, ``skip_animations``) from the
timeline. Click one to jump there; **Loop** sets the play range to it; **Export
section** opens the Export dialog for its range; **Export all** ticks Manim's
``--save_sections``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROLE = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class SectionSpan:
    name: str
    start: int  # frames, half-open
    end: int
    type: str
    skip: bool


def section_spans(timeline: dict[str, Any]) -> list[SectionSpan]:
    """Each section from its start to the next one (or the end of the scene). The
    implicit first section is listed as "(start)" when it has frames."""
    total = int(timeline.get("duration_frames", 0))
    marks = sorted(
        (e for e in timeline.get("events", []) if e["kind"] == "section"),
        key=lambda e: e["start_frame"],
    )
    spans: list[SectionSpan] = []
    if not marks or marks[0]["start_frame"] > 0:
        first = marks[0]["start_frame"] if marks else total
        if first > 0:
            spans.append(SectionSpan("(start)", 0, first, "default", False))
    for i, e in enumerate(marks):
        end = marks[i + 1]["start_frame"] if i + 1 < len(marks) else total
        meta = e.get("meta") or {}
        spans.append(
            SectionSpan(
                e.get("label", ""),
                int(e["start_frame"]),
                int(end),
                str(meta.get("type") or "default"),
                bool(meta.get("skip_animations")),
            )
        )
    return spans


class SectionsPanel(QWidget):
    seekRequested = Signal(int)
    loopRequested = Signal(int, int)
    exportRequested = Signal(int, int)
    exportAllRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Sections")
        self.fps = 15.0
        self.spans: list[SectionSpan] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()  # never let this panel's minimum width widen the dock
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 6, 6, 6)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Scene sections")
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderLabels(["section", "start", "length", "type"])
        self.tree.setColumnWidth(0, 170)
        lay.addWidget(self.tree, 1)
        self.empty = QLabel('No sections. Add one with <code>self.next_section("Name")</code>.')
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        row = QHBoxLayout()
        self.loop_btn = QPushButton("Loop")
        self.loop_btn.setAccessibleName("Loop the selected section")
        self.export_btn = QPushButton("Export section…")
        self.export_btn.setAccessibleName("Export the selected section")
        self.all_btn = QPushButton("Export all…")
        self.all_btn.setAccessibleName("Export every section as its own video")
        for b in (self.loop_btn, self.export_btn, self.all_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.tree.itemClicked.connect(
            lambda it, _c: self.seekRequested.emit(it.data(0, ROLE).start)
        )
        self.tree.currentItemChanged.connect(lambda *_: self._buttons())
        self.loop_btn.clicked.connect(lambda: self._emit(self.loopRequested))
        self.export_btn.clicked.connect(lambda: self._emit(self.exportRequested))
        self.all_btn.clicked.connect(self.exportAllRequested.emit)
        self._buttons()

    def set_timeline(self, timeline: dict[str, Any] | None) -> None:
        keep = self.selected().name if self.selected() else None
        self.tree.clear()
        self.spans = section_spans(timeline) if timeline else []
        self.fps = float(timeline.get("frame_rate", 15)) if timeline else 15.0
        named = [s for s in self.spans if s.name != "(start)"]
        self.empty.setVisible(not named)
        for s in self.spans:
            label = s.name + ("  (skipped)" if s.skip else "")
            it = QTreeWidgetItem(
                [
                    label,
                    f"{s.start / self.fps:.2f}s",
                    f"{(s.end - s.start) / self.fps:.2f}s",
                    s.type,
                ]
            )
            it.setData(0, ROLE, s)
            if s.skip:
                it.setToolTip(0, "skip_animations=True: Manim leaves this section out of the video")
            self.tree.addTopLevelItem(it)
            if s.name == keep:
                self.tree.setCurrentItem(it)
        self.all_btn.setEnabled(bool(named))
        self._buttons()

    def selected(self) -> SectionSpan | None:
        it = self.tree.currentItem()
        return it.data(0, ROLE) if it else None

    def _buttons(self) -> None:
        ok = self.selected() is not None
        self.loop_btn.setEnabled(ok)
        self.export_btn.setEnabled(ok)

    def _emit(self, signal: Any) -> None:
        s = self.selected()
        if s:
            signal.emit(s.start, s.end)
