"""Project panel: the project theme and the variables scenes read (spec F07).

Theme colours (semantic names, Manim colour constants as defaults), Text font, code
font and code style, and one typed editor per project variable the current scene
read via ``project.var(...)`` (the explicit opt-in the spec asks for). **Apply** writes
``.manim-stage/project.json`` (validated, atomic, undoable) and re-renders.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ... import project as pj


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, value: str, name: str) -> None:
        super().__init__()
        self.setAccessibleName(name)
        self.set_value(value)
        self.clicked.connect(self._pick)

    def set_value(self, value: str) -> None:
        self.value = value
        self.setText(value.upper())
        fg = "#000000" if QColor(value).lightness() > 128 else "#ffffff"
        self.setStyleSheet(
            f"background:{value}; color:{fg}; border:1px solid #777; padding:2px 8px"
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self.value), self, self.accessibleName())
        if c.isValid():
            self.set_value(c.name())
            self.changed.emit(self.value)


class ProjectPanel(QWidget):
    applyRequested = Signal(object)  # ProjectEdit

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Project theme and variables")
        self.path = None
        self.saved: dict[str, Any] = {}
        self.used: list[dict[str, Any]] = []
        self.color_buttons: dict[str, ColorButton] = {}
        self.var_editors: dict[str, Any] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
        row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setAccessibleName("Save the project theme and variables")
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.setAccessibleName("Discard unsaved project changes")
        row.addStretch(1)
        row.addWidget(self.revert_btn)
        row.addWidget(self.apply_btn)
        outer.addLayout(row)
        self.apply_btn.clicked.connect(self._apply)
        self.revert_btn.clicked.connect(self.reload)

    # -- data -------------------------------------------------------------------------

    def set_project(self, path: Any, used_variables: list[dict[str, Any]] | None = None) -> None:
        self.path = path
        if used_variables is not None:
            self.used = used_variables
        self.reload()

    def reload(self) -> None:
        if self.path is None:
            return
        try:
            proj = pj.load(self.path)
        except pj.ProjectError as e:
            self.note.setText(f"⚠ {e}")
            return
        self.saved = proj.to_dict()
        self.note.setText(f"{self.path.parent.parent.name}/.manim-stage/project.json"
                          + ("" if self.path.exists() else " (not created yet)"))  # fmt: skip
        self._build(proj)

    def _build(self, proj: pj.Project) -> None:
        body = QWidget()
        form = QFormLayout(body)
        form.addRow(QLabel("<b>Theme colours</b>"))
        self.color_buttons = {}
        for name, value in proj.theme.colors.items():
            b = ColorButton(value, f"Theme colour {name}")
            self.color_buttons[name] = b
            form.addRow(name, b)
        self.font_edit = QLineEdit(proj.theme.font or "")
        self.font_edit.setPlaceholderText("Manim default")
        self.font_edit.setAccessibleName("Text font")
        form.addRow("Text font", self.font_edit)
        self.code_font_edit = QLineEdit(proj.theme.code_font or "")
        self.code_font_edit.setPlaceholderText("JetBrains Mono (bundled)")
        self.code_font_edit.setAccessibleName("Code font")
        form.addRow("Code font", self.code_font_edit)
        self.code_style = QComboBox()
        self.code_style.setAccessibleName("Code style")
        self.code_style.addItem("(monokai)", "")
        from pygments.styles import get_all_styles

        for st in sorted(get_all_styles()):
            self.code_style.addItem(st, st)
        idx = self.code_style.findData(proj.theme.code_style or "")
        self.code_style.setCurrentIndex(max(idx, 0))
        form.addRow("Code style", self.code_style)
        self.tex_template = QComboBox()
        self.tex_template.setAccessibleName("TeX template")
        self.tex_template.addItem("(Manim default)", "")
        from ...typography import tex_templates

        for name in tex_templates():
            self.tex_template.addItem(name, name)
        idx = self.tex_template.findData(proj.theme.tex_template or "")
        self.tex_template.setCurrentIndex(max(idx, 0))
        form.addRow("TeX template", self.tex_template)

        form.addRow(QLabel("<b>Variables</b>"))
        self.var_editors = {}
        known = {v["name"]: v for v in self.used}
        for name, v in proj.variables.items():
            known.setdefault(name, {"name": name, **v.to_dict()})
        if not known:
            form.addRow(QLabel('None yet. Read one in a scene with project.var("name", default).'))
        for name in sorted(known):
            info = dict(known[name])
            stored = proj.variables.get(name)
            if stored is not None and stored.value is not None:
                info["value"] = stored.value
            editor = self._editor(name, info)
            self.var_editors[name] = (editor, info)
            label = name + (f" — {info['description']}" if info.get("description") else "")
            form.addRow(label, editor)
        self.scroll.setWidget(body)

    def _editor(self, name: str, info: dict[str, Any]) -> QWidget:
        kind, value = info.get("type"), info.get("value", info.get("default"))
        if kind == "number":
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setRange(info.get("min") if info.get("min") is not None else -1e9,
                       info.get("max") if info.get("max") is not None else 1e9)  # fmt: skip
            w.setValue(float(value or 0))
        elif kind == "integer":
            w = QSpinBox()
            w.setRange(int(info.get("min") if info.get("min") is not None else -10**9),
                       int(info.get("max") if info.get("max") is not None else 10**9))  # fmt: skip
            w.setValue(int(value or 0))
        elif kind == "boolean":
            w = QCheckBox()
            w.setChecked(bool(value))
        elif kind == "color":
            w = ColorButton(str(value or "#ffffff"), f"Variable {name}")
        elif kind == "enum":
            w = QComboBox()
            for opt in info.get("options") or []:
                w.addItem(str(opt), opt)
            w.setCurrentIndex(max(w.findData(value), 0))
        else:
            w = QLineEdit(str(value or ""))
        w.setAccessibleName(f"Variable {name}")
        return w

    # -- apply ------------------------------------------------------------------------

    def collected(self) -> dict[str, Any]:
        """The project document as edited in the panel."""
        d = copy.deepcopy(self.saved) or {"schema": pj.SCHEMA, "version": pj.VERSION}
        theme = d.setdefault("theme", {})
        theme["colors"] = {n: b.value for n, b in self.color_buttons.items()}
        for key, edit in (("font", self.font_edit), ("code_font", self.code_font_edit)):
            if edit.text().strip():
                theme[key] = edit.text().strip()
            else:
                theme.pop(key, None)
        if self.tex_template.currentData():
            theme["tex_template"] = self.tex_template.currentData()
        else:
            theme.pop("tex_template", None)
        if self.code_style.currentData():
            theme["code_style"] = self.code_style.currentData()
        else:
            theme.pop("code_style", None)
        variables = d.setdefault("variables", {})
        for name, (w, info) in self.var_editors.items():
            kind = info.get("type")
            if kind in ("number", "integer"):
                value: Any = w.value()
            elif kind == "boolean":
                value = w.isChecked()
            elif kind == "color":
                value = w.value
            elif kind == "enum":
                value = w.currentData()
            else:
                value = w.text()
            entry = {k: v for k, v in info.items() if k not in ("name", "value") and v is not None}
            entry["value"] = value
            variables[name] = entry
        if not variables:
            d.pop("variables", None)
        return d

    def has_changes(self) -> bool:
        return json.dumps(self.collected(), sort_keys=True) != json.dumps(
            self.saved, sort_keys=True
        )

    def _apply(self) -> None:
        if self.path is None or not self.has_changes():
            return
        self.applyRequested.emit(
            pj.ProjectEdit(self.saved, self.collected(), "Edit project theme/variables")
        )
