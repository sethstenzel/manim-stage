"""Export dialog: render with Manim's CLI, with progress, cancel and a result summary.

Settings use Manim's own vocabulary: quality presets (``-ql`` … ``-qk``), output
``--format``, ``-t`` transparency, ``--save_sections``, ``-n`` animation range,
``--media_dir`` and ``-o``. The exact command is shown and can be copied, so the same
render can be reproduced headlessly (spec §13).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ...export import (
    ALPHA_FORMATS,
    FORMATS,
    ExportJob,
    ExportResult,
    ExportSettings,
    display_command,
    frames_for_play_range,
    manim_command,
    play_range_for_frames,
)
from .quality import manim_qualities, quality_label

FORMAT_LABELS = {
    "mp4": "MP4 video (H.264)",
    "webm": "WebM video (VP9)",
    "mov": "MOV video (QuickTime)",
    "gif": "GIF animation",
    "png-sequence": "PNG image sequence",
    "png": "PNG (last frame)",
}


class ExportDialog(QDialog):
    def __init__(
        self,
        file: Path,
        scene: str,
        timeline: dict[str, Any] | None,
        range_frames: tuple[int, int] | None,
        fps: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Export {scene}")
        self.setAccessibleName("Export dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.file, self.scene, self.timeline, self.fps = file, scene, timeline, fps
        self.range_frames = range_frames
        self.job: ExportJob | None = None
        self.result: ExportResult | None = None
        self._queue: deque[tuple[str, Any]] = deque()  # filled by the job's thread

        form = QFormLayout()
        self.quality = QComboBox()
        self.quality.setAccessibleName("Quality")
        for key, q in manim_qualities().items():
            self.quality.addItem(quality_label(key, q), key)
        self.quality.setCurrentIndex(max(self.quality.findData("high_quality"), 0))
        form.addRow("Quality", self.quality)
        self.format = QComboBox()
        self.format.setAccessibleName("Format")
        for f in FORMATS:
            self.format.addItem(FORMAT_LABELS[f], f)
        form.addRow("Format", self.format)
        self.transparent = QCheckBox("Transparent background (-t)")
        self.transparent.setAccessibleName("Transparent background")
        form.addRow("", self.transparent)
        self.sections = QCheckBox("Also save each section as its own video (--save_sections)")
        self.sections.setAccessibleName("Save sections")
        form.addRow("", self.sections)

        self.whole = QRadioButton("Whole scene")
        self.whole.setChecked(True)
        self.ranged = QRadioButton("In/out range")
        self.ranged.setEnabled(bool(range_frames and timeline))
        self.range_note = QLabel("")
        self.range_note.setWordWrap(True)
        rbox = QVBoxLayout()
        rbox.addWidget(self.whole)
        rbox.addWidget(self.ranged)
        rbox.addWidget(self.range_note)
        form.addRow("Range", rbox)

        self.media_dir = QLineEdit("media")
        self.media_dir.setToolTip("Relative folders are relative to the scene file's folder")
        self.media_dir.setAccessibleName("Media folder (--media_dir)")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        mrow = QHBoxLayout()
        mrow.addWidget(self.media_dir, 1)
        mrow.addWidget(browse)
        form.addRow("Media folder", mrow)
        self.name = QLineEdit(scene)
        self.name.setAccessibleName("Output name (-o)")
        form.addRow("Output name", self.name)

        self.command = QLineEdit()
        self.command.setReadOnly(True)
        self.command.setAccessibleName("Manim command")
        copy = QPushButton("Copy")
        copy.setAccessibleName("Copy the Manim command")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.command.text()))
        crow = QHBoxLayout()
        crow.addWidget(self.command, 1)
        crow.addWidget(copy)
        form.addRow("Command", crow)

        self.progress = QProgressBar()
        self.progress.setAccessibleName("Export progress")
        self.progress.setRange(0, 1000)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Export status")
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setAccessibleName("Manim output")
        self.log.setVisible(False)

        self.export_btn = QPushButton("Export")
        self.export_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        self.open_btn = QPushButton("Show in folder")
        self.open_btn.setEnabled(False)
        self.log_btn = QPushButton("Show log")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(self.log.setVisible)
        brow = QHBoxLayout()
        brow.addWidget(self.log_btn)
        brow.addStretch(1)
        for b in (self.open_btn, self.cancel_btn, self.export_btn):
            brow.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        lay.addWidget(self.log, 1)
        lay.addLayout(brow)
        self.resize(720, 440)

        for w in (self.quality, self.format):
            w.currentIndexChanged.connect(self._refresh)
        for w in (self.transparent, self.sections, self.whole, self.ranged):
            w.toggled.connect(self._refresh)
        for w in (self.media_dir, self.name):
            w.textChanged.connect(self._refresh)
        self.export_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self._cancel_or_close)
        self.open_btn.clicked.connect(self._open_folder)
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._drain)
        self._poll.start(30)
        if range_frames and timeline:
            self.ranged.setChecked(True)
        self._refresh()

    # -- settings ---------------------------------------------------------------------

    def settings(self) -> ExportSettings:
        fmt = self.format.currentData()
        play_range = None
        if self.ranged.isChecked() and self.range_frames and self.timeline:
            play_range = play_range_for_frames(self.timeline, *self.range_frames)
        return ExportSettings(
            quality=self.quality.currentData(),
            format=fmt,
            transparent=self.transparent.isChecked() and fmt in ALPHA_FORMATS,
            save_sections=self.sections.isChecked(),
            play_range=play_range,
            media_dir=Path(self.media_dir.text()).expanduser(),
            output_name=self.name.text().strip() or None,
        )

    def _refresh(self) -> None:
        fmt = self.format.currentData()
        self.transparent.setEnabled(fmt in ALPHA_FORMATS)
        s = self.settings()
        if s.play_range and self.timeline:
            a, b = frames_for_play_range(self.timeline, s.play_range)
            self.range_note.setText(
                f"Manim renders whole animations: animations {s.play_range[0]}–{s.play_range[1]}"
                f" (preview frames {a}–{b - 1}, {a / self.fps:.2f}–{b / self.fps:.2f} s)."
            )
        else:
            self.range_note.setText("")
        # Shown as run from the scene's folder (that's where Manim resolves relative paths).
        self.command.setText(display_command(manim_command(Path(self.file.name), self.scene, s)))
        self.command.setToolTip(f"Run in: {self.file.parent}")

    def _browse(self) -> None:
        start = Path(self.media_dir.text())
        start = start if start.is_absolute() else self.file.parent / start
        d = QFileDialog.getExistingDirectory(self, "Media folder", str(start))
        if d:
            self.media_dir.setText(d)

    # -- running ----------------------------------------------------------------------

    def start(self) -> None:
        self.result = None
        self.export_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        self.progress.setValue(0)
        self.status.setText("Starting Manim…")
        self.log.clear()
        total = None
        if self.timeline:
            total = sum(1 for e in self.timeline["events"] if e["kind"] in ("play", "wait"))
        self.job = ExportJob(
            self.file,
            self.scene,
            self.settings(),
            total_plays=total,
            on_progress=lambda f, m: self._queue.append(("progress", (f, m))),
            on_log=lambda line: self._queue.append(("log", line)),
            on_done=lambda r: self._queue.append(("done", r)),
        ).start()

    def _drain(self) -> None:
        while self._queue:
            kind, data = self._queue.popleft()
            if kind == "progress":
                f, msg = data
                self.progress.setValue(int(f * 1000))
                self.status.setText(msg)
            elif kind == "log":
                self.log.appendPlainText(data)
            elif kind == "done":
                self._done(data)

    def _done(self, r: ExportResult) -> None:
        self.result = r
        self.job = None
        self.export_btn.setEnabled(True)
        self.export_btn.setText("Export again")
        self.cancel_btn.setText("Close")
        if r.cancelled:
            self.status.setText("Cancelled.")
            return
        if not r.ok:
            self.status.setText(f"⚠ Export failed. {r.error}")
            self.log_btn.setChecked(True)
            return
        self.open_btn.setEnabled(True)
        p = r.probe
        try:
            shown = str(r.output.relative_to(self.file.parent))
        except ValueError:
            shown = str(r.output)
        bits = [shown]
        if p:
            audio = f"audio {p['audio'][0]['codec']}" if p.get("audio") else "no audio"
            vfr = " · ⚠ variable frame rate" if p.get("variable_frame_rate") else ""
            bits.append(
                f"{p.get('width')}×{p.get('height')} · {p.get('fps'):g} fps · "
                f"{p.get('duration_s', 0):.2f} s · {p.get('video_codec')} · {audio}{vfr}"
            )
        self.status.setText("✔ Done: " + "\n".join(bits))

    def _cancel_or_close(self) -> None:
        if self.job is not None:
            self.job.cancel()
        else:
            self.close()

    def _open_folder(self) -> None:
        if self.result and self.result.output:
            folder = (
                self.result.output if self.result.output.is_dir() else self.result.output.parent
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, e: Any) -> None:  # noqa: N802
        if self.job is not None:
            self.job.cancel()
        self._poll.stop()
        super().closeEvent(e)
