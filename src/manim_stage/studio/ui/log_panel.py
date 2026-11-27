"""Log and error panel with jump-to-source (spec F01: traceback with file/line)."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MAX_LOG_LINES = 5000


def editor_command(file: str, line: int | None) -> list[str] | None:
    """Command that opens ``file`` at ``line`` in the user's code editor, if known.

    ``MANIM_STAGE_EDITOR`` is a template such as ``code -g {file}:{line}`` or
    ``subl {file}:{line}``. Without it, VS Code is used if it is on PATH.
    """
    template = os.environ.get("MANIM_STAGE_EDITOR")
    if template:
        parts = shlex.split(template, posix=os.name != "nt")
        return [p.format(file=file, line=line or 1) for p in parts]
    code = shutil.which("code")
    if code:
        return [code, "-g", f"{file}:{line or 1}"]
    return None


def open_in_editor(file: str, line: int | None) -> None:
    cmd = editor_command(file, line)
    if cmd:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)  # fmt: skip
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(file))


class LogPanel(QWidget):
    openSource = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Log and errors")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        self.error_label = QLabel("")
        self.error_label.setAccessibleName("Error")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self.open_button = QPushButton("Open in editor")
        self.open_button.setAccessibleName("Open error location in code editor")
        self.open_button.setVisible(False)
        row.addWidget(self.error_label, 1)
        row.addWidget(self.open_button)
        lay.addLayout(row)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Log")
        self.text.setMaximumBlockCount(MAX_LOG_LINES)  # bounded (spec §4: no unbounded buffers)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        lay.addWidget(self.text)
        self._error_loc: tuple[str, int] | None = None
        self.open_button.clicked.connect(self._open)

    def append(self, line: str) -> None:
        self.text.appendPlainText(line)

    def show_error(self, message: str, file: str | None, line: int | None, tb: str) -> None:
        where = f"{Path(file).name}:{line}" if file and line else (file or "")
        self.error_label.setText(f"⚠ {message}" + (f"  —  {where}" if where else ""))
        self.error_label.setVisible(True)
        self._error_loc = (file, line or 1) if file else None
        self.open_button.setVisible(self._error_loc is not None)
        self.open_button.setText(f"Open {where}" if where else "Open in editor")
        if tb:
            self.text.appendPlainText(tb.rstrip())

    def clear_error(self) -> None:
        self.error_label.setVisible(False)
        self.open_button.setVisible(False)
        self._error_loc = None

    @property
    def error_location(self) -> tuple[str, int] | None:
        return self._error_loc

    def _open(self) -> None:
        if self._error_loc:
            self.openSource.emit(*self._error_loc)
