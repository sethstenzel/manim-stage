"""Config tab: the scene folder's ``manim.cfg`` [CLI] defaults (backlog MF.6).

Edits the keys plain ``manim render`` reads (background, size, frame rate, format,
transparency, sections, renderer, media folder). **Apply** writes ``manim.cfg``
(undoable; other sections and keys are kept) and re-renders. Empty fields fall back
to Manim's defaults, shown as placeholders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import manimcfg


class ConfigPanel(QWidget):
    applyRequested = Signal(object)  # manimcfg.CfgEdit

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Manim config")
        self.path: Path | None = None
        self.saved: dict[str, str] = {}
        self.editors: dict[str, Any] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
        self.renderer_note = QLabel("")
        self.renderer_note.setWordWrap(True)
        outer.addWidget(self.renderer_note)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        outer.addWidget(self.error)
        row = QHBoxLayout()
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setAccessibleName("Discard unsaved manim.cfg changes")
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setAccessibleName("Save manim.cfg")
        row.addStretch(1)
        row.addWidget(self.revert_btn)
        row.addWidget(self.apply_btn)
        outer.addLayout(row)
        self.apply_btn.clicked.connect(self._apply)
        self.revert_btn.clicked.connect(self.reload)

    def set_path(self, path: Path) -> None:
        self.path = Path(path)
        self.reload()

    def reload(self) -> None:
        if self.path is None:
            return
        self.error.setText("")
        self.saved = manimcfg.read(self.path)
        effective = manimcfg.effective(self.path)
        exists = self.path.is_file()
        self.note.setText(
            f"<b>{self.path.name}</b> in the scene folder"
            + ("" if exists else " (not created yet)")
            + ": defaults for <code>manim render</code> there, Studio exports included."
            " Preview size and fps follow the Quality menu."
        )
        body = QWidget()
        form = QFormLayout(body)
        self.editors = {}
        for key in manimcfg.KEYS:
            current = self.saved.get(key.name, "")
            default = "" if effective.get(key.name) is None else str(effective[key.name])
            if key.type in ("enum", "boolean"):
                w: Any = QComboBox()
                w.addItem(f"(Manim default: {default})" if default else "(Manim default)", "")
                opts = key.options if key.type == "enum" else ("True", "False")
                for o in opts:
                    w.addItem(o, o)
                w.setCurrentIndex(max(w.findData(current), 0))
            else:
                w = QLineEdit(current)
                w.setPlaceholderText(default)
            w.setAccessibleName(key.label)
            label = key.label + (" ◐" if key.preview else "")
            form.addRow(label, w)
            self.editors[key.name] = w
        self.scroll.setWidget(body)
        renderer = self.saved.get("renderer") or str(effective.get("renderer") or "cairo")
        self.renderer_note.setText(
            "◐ also changes the preview. Preview renderer: <b>Cairo</b>"
            + (
                " (exports use <b>OpenGL</b>; the preview never substitutes it silently)"
                if renderer == "opengl"
                else ""
            )
        )

    def collected(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for name, w in self.editors.items():
            v = w.currentData() if isinstance(w, QComboBox) else w.text().strip()
            out[name] = v or None
        return out

    def _apply(self) -> None:
        if self.path is None:
            return
        values = self.collected()
        if {k: v for k, v in values.items() if v} == self.saved:
            self.error.setText("No changes.")
            return
        try:
            edit = manimcfg.edit_for(self.path, values)
        except manimcfg.ConfigError as e:
            self.error.setText(f"⚠ {e}")
            return
        self.error.setText("")
        self.applyRequested.emit(edit)
