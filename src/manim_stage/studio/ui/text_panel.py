"""Text tab: font picker and LaTeX formula helper (backlog MF.10).

- **Fonts:** every font Pango (Manim's ``Text``) can use, each shown in its own face
  with your sample text. **Copy Python** gives ``Text("…", font="…")``; **Use as project
  font** sets the project theme's font (undoable), which ``StageScene`` applies to all
  ``Text``/``MarkupText``.
- **LaTeX:** a formula, coloured parts (``x: BLUE, \\pi: #FF0000`` → Manim's
  ``tex_to_color_map``) and a TeX template. **Preview** renders it with Manim (needs
  LaTeX); **Copy Python** gives the ``MathTex(...)`` call; **Use template for project**
  sets ``theme.tex_template``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import typography as ty


class TextPanel(QWidget):
    themeRequested = Signal(str, str)  # theme key ("font" | "tex_template"), value
    copied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Text and LaTeX")
        self._loaded = False
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

        fbox = QGroupBox("Fonts (Text, MarkupText)")
        fl = QVBoxLayout(fbox)
        row = QHBoxLayout()
        self.font_search = QLineEdit()
        self.font_search.setPlaceholderText("Search fonts…")
        self.font_search.setAccessibleName("Search fonts")
        self.font_search.setClearButtonEnabled(True)
        self.sample = QLineEdit("Bubble sort, O(n²)")
        self.sample.setAccessibleName("Sample text")
        row.addWidget(self.font_search, 1)
        row.addWidget(self.sample, 1)
        fl.addLayout(row)
        self.font_list = QListWidget()
        self.font_list.setAccessibleName("Fonts")
        fl.addWidget(self.font_list, 1)
        frow = QHBoxLayout()
        self.font_copy = QPushButton("Copy Python")
        self.font_copy.setAccessibleName("Copy the Text call with this font")
        self.font_use = QPushButton("Use as project font")
        self.font_use.setAccessibleName("Set the project theme font")
        frow.addWidget(self.font_copy)
        frow.addWidget(self.font_use)
        frow.addStretch(1)
        fl.addLayout(frow)
        lay.addWidget(fbox, 3)

        tbox = QGroupBox("LaTeX (MathTex, Tex)")
        tl = QVBoxLayout(tbox)
        self.latex_note = QLabel("")
        self.latex_note.setWordWrap(True)
        tl.addWidget(self.latex_note)
        form = QFormLayout()
        self.tex = QPlainTextEdit(r"e^{i\pi} + 1 = 0")
        self.tex.setAccessibleName("LaTeX formula")
        self.tex.setMaximumHeight(60)
        form.addRow("Formula", self.tex)
        self.colors = QLineEdit(r"e: BLUE, \pi: YELLOW")
        self.colors.setAccessibleName("Coloured parts")
        self.colors.setToolTip("substring: colour, … (Manim colour names or #RRGGBB)")
        form.addRow("Colours", self.colors)
        self.template = QComboBox()
        self.template.setAccessibleName("TeX template")
        form.addRow("Template", self.template)
        tl.addLayout(form)
        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        tl.addWidget(self.warn)
        self.snippet = QPlainTextEdit()
        self.snippet.setReadOnly(True)
        self.snippet.setAccessibleName("MathTex snippet")
        self.snippet.setMaximumHeight(56)
        tl.addWidget(self.snippet)
        self.preview = QLabel("")
        self.preview.setAccessibleName("Formula preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(70)
        tl.addWidget(self.preview)
        trow = QHBoxLayout()
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setAccessibleName("Render the formula with LaTeX")
        self.tex_copy = QPushButton("Copy Python")
        self.tex_copy.setAccessibleName("Copy the MathTex call")
        self.tex_use = QPushButton("Use template for project")
        self.tex_use.setAccessibleName("Set the project TeX template")
        for b in (self.preview_btn, self.tex_copy, self.tex_use):
            trow.addWidget(b)
        trow.addStretch(1)
        tl.addLayout(trow)
        lay.addWidget(tbox, 2)

        self.font_search.textChanged.connect(self._filter_fonts)
        self.sample.textChanged.connect(self._resample)
        self.font_list.currentItemChanged.connect(lambda *_: self._font_buttons())
        self.font_copy.clicked.connect(self.copy_font)
        self.font_use.clicked.connect(
            lambda: self.current_font() and self.themeRequested.emit("font", self.current_font())
        )
        for sig in (self.tex.textChanged, self.colors.textChanged):
            sig.connect(self._update_snippet)
        self.template.currentIndexChanged.connect(self._update_snippet)
        self.tex_copy.clicked.connect(self.copy_tex)
        self.preview_btn.clicked.connect(self.render_preview)
        self.tex_use.clicked.connect(
            lambda: self.themeRequested.emit("tex_template", self.template.currentData() or "")
        )

    # -- lazy load (fonts and Manim templates take a moment) --------------------------

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt)
        super().showEvent(event)
        self.load()

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        for fam in ty.fonts():
            it = QListWidgetItem(f"{fam} — {self.sample.text()}")
            it.setData(Qt.ItemDataRole.UserRole, fam)
            it.setFont(QFont(fam, 13))
            self.font_list.addItem(it)
        self.template.addItem("default", "default")
        for name in ty.tex_templates():
            if name != "default":
                self.template.addItem(name, name)
        st = ty.latex_status()
        self.latex_ok = st["ok"]
        self.latex_note.setText(
            "LaTeX found."
            if st["ok"]
            else "⚠ LaTeX not found (needs <code>latex</code> and <code>dvisvgm</code>): "
            "preview is off, snippets still work. See <code>manim-stage doctor</code>."
        )
        self.preview_btn.setEnabled(st["ok"])
        self._font_buttons()
        self._update_snippet()

    # -- fonts ------------------------------------------------------------------------

    def _filter_fonts(self, text: str) -> None:
        q = text.lower().strip()
        for i in range(self.font_list.count()):
            it = self.font_list.item(i)
            it.setHidden(bool(q) and q not in it.data(Qt.ItemDataRole.UserRole).lower())

    def _resample(self, text: str) -> None:
        for i in range(self.font_list.count()):
            it = self.font_list.item(i)
            it.setText(f"{it.data(Qt.ItemDataRole.UserRole)} — {text}")

    def current_font(self) -> str:
        it = self.font_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def _font_buttons(self) -> None:
        ok = bool(self.current_font())
        self.font_copy.setEnabled(ok)
        self.font_use.setEnabled(ok)

    def copy_font(self) -> None:
        if self.current_font():
            QGuiApplication.clipboard().setText(
                ty.text_snippet(self.sample.text(), self.current_font())
            )
            self.copied.emit(self.current_font())

    # -- LaTeX ------------------------------------------------------------------------

    def tex_state(self) -> tuple[str, dict[str, str], str]:
        return (
            self.tex.toPlainText().strip(),
            ty.parse_color_map(self.colors.text()),
            self.template.currentData() or "default",
        )

    def _update_snippet(self) -> None:
        if not self._loaded:
            return
        tex, colors, template = self.tex_state()
        self.snippet.setPlainText(ty.mathtex_snippet(tex, colors, template))
        missing = ty.missing_substrings(tex, colors)
        self.warn.setText(f"⚠ Not in the formula: {', '.join(missing)}" if missing else "")

    def copy_tex(self) -> None:
        QGuiApplication.clipboard().setText(self.snippet.toPlainText())
        self.copied.emit("MathTex")

    def render_preview(self) -> None:
        tex, colors, template = self.tex_state()
        out = Path(tempfile.gettempdir()) / "manim-stage-tex-preview.png"
        self.preview.setText("Rendering…")
        QGuiApplication.processEvents()
        try:
            ty.render_tex_png(tex, colors, template, out)
        except Exception as e:  # LaTeX errors are shown, not raised
            self.preview.setText(f"⚠ {str(e)[-300:]}")
            return
        pm = QPixmap(str(out))
        self.preview.setPixmap(
            pm.scaledToHeight(min(90, pm.height()), Qt.TransformationMode.SmoothTransformation)
        )
