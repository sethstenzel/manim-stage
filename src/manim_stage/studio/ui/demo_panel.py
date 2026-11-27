"""Demo tab: live controls for the scene's demo parameters (spec F12, backlog 4.3).

One control per ``demo.param(...)`` the scene read: a slider for bounded numbers, a
check box, a list, a colour button or a text field. Moving a control re-renders the
preview after a short pause. Values are editor-time only; exports use the defaults
unless *Bake demo values* is ticked in the Export dialog.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .project_panel import ColorButton

SLIDER_STEPS = 1000


class _NumberControl(QWidget):
    """Slider + spin box for a bounded number or integer."""

    changed = Signal()

    def __init__(self, info: dict[str, Any], value: Any, name: str) -> None:
        super().__init__()
        self.integer = info["type"] == "integer"
        self.lo, self.hi = float(info["min"]), float(info["max"])
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName(f"Demo parameter {name}")
        if self.integer:
            self.slider.setRange(int(self.lo), int(self.hi))
            self.spin: QSpinBox | QDoubleSpinBox = QSpinBox()
            self.spin.setRange(int(self.lo), int(self.hi))
        else:
            self.slider.setRange(0, SLIDER_STEPS)
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(3)
            self.spin.setRange(self.lo, self.hi)
            if info.get("step"):
                self.spin.setSingleStep(float(info["step"]))
        self.spin.setAccessibleName(f"Demo parameter {name} value")
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.set_value(value)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _to_slider(self, v: float) -> int:
        if self.integer:
            return int(v)
        span = (self.hi - self.lo) or 1.0
        return round((v - self.lo) / span * SLIDER_STEPS)

    def set_value(self, v: Any) -> None:
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        self.spin.setValue(int(v) if self.integer else float(v))
        self.slider.setValue(self._to_slider(float(v)))
        for w in (self.slider, self.spin):
            w.blockSignals(False)

    def value(self) -> Any:
        return self.spin.value()

    def _from_slider(self, s: int) -> None:
        v = s if self.integer else self.lo + (self.hi - self.lo) * s / SLIDER_STEPS
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.changed.emit()

    def _from_spin(self, v: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_slider(v))
        self.slider.blockSignals(False)
        self.changed.emit()


class DemoPanel(QWidget):
    valuesChanged = Signal(dict)  # {name: value} differing from the defaults

    def __init__(self, parent: QWidget | None = None, debounce_ms: int = 250) -> None:
        super().__init__(parent)
        self.setAccessibleName("Demo parameters")
        self.params: list[dict[str, Any]] = []
        self.controls: dict[str, tuple[QWidget, dict[str, Any]]] = {}
        self.values: dict[str, Any] = {}  # current overrides (not saved anywhere)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        note = QLabel(
            "Editor-time controls for this scene's <code>demo.param(...)</code> values. "
            "Exports use the defaults unless you tick <i>Bake demo values</i>."
        )
        note.setWordWrap(True)
        outer.addWidget(note)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)
        row = QHBoxLayout()
        self.live = QCheckBox("Live")
        self.live.setChecked(True)
        self.live.setAccessibleName("Re-render as controls change")
        self.update_btn = QPushButton("Update")
        self.update_btn.setAccessibleName("Re-render with these demo values")
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setAccessibleName("Reset demo parameters to their defaults")
        row.addWidget(self.live)
        row.addStretch(1)
        row.addWidget(self.reset_btn)
        row.addWidget(self.update_btn)
        outer.addLayout(row)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._emit)
        self.update_btn.clicked.connect(self._emit)
        self.reset_btn.clicked.connect(self.reset)
        self._build()

    def set_params(self, params: list[dict[str, Any]]) -> None:
        """The parameters the last render read (from the timeline message)."""
        if [(p["name"], p.get("type")) for p in params] == [
            (p["name"], p.get("type")) for p in self.params
        ]:
            self.params = params  # same knobs: keep the controls (and focus) as they are
            return
        self.params = params
        names = {p["name"] for p in params}
        self.values = {k: v for k, v in self.values.items() if k in names}
        self._build()

    def _build(self) -> None:
        body = QWidget()
        form = QFormLayout(body)
        self.controls = {}
        if not self.params:
            form.addRow(
                QLabel(
                    'None. Add one in a scene: <code>n = demo.param("n", 6, min=2, max=12)</code>'
                )
            )
        for info in self.params:
            name = info["name"]
            value = self.values.get(name, info.get("default"))
            w = self._control(name, info, value)
            self.controls[name] = (w, info)
            label = name + (f" — {info['description']}" if info.get("description") else "")
            form.addRow(label, w)
        self.scroll.setWidget(body)

    def _control(self, name: str, info: dict[str, Any], value: Any) -> QWidget:
        kind = info.get("type")
        bounded = info.get("min") is not None and info.get("max") is not None
        if kind in ("number", "integer") and bounded:
            w: Any = _NumberControl(info, value, name)
            w.changed.connect(self._changed)
            return w
        if kind == "number":
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setRange(-1e9, 1e9)
            w.setValue(float(value))
            w.valueChanged.connect(self._changed)
        elif kind == "integer":
            w = QSpinBox()
            w.setRange(-(10**9), 10**9)
            w.setValue(int(value))
            w.valueChanged.connect(self._changed)
        elif kind == "boolean":
            w = QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(self._changed)
        elif kind == "color":
            w = ColorButton(str(value), f"Demo parameter {name}")
            w.changed.connect(self._changed)
        elif kind == "enum":
            w = QComboBox()
            for opt in info.get("options") or []:
                w.addItem(str(opt), opt)
            w.setCurrentIndex(max(w.findData(value), 0))
            w.currentIndexChanged.connect(self._changed)
        else:
            w = QLineEdit(str(value))
            w.editingFinished.connect(self._changed)
        w.setAccessibleName(f"Demo parameter {name}")
        return w

    @staticmethod
    def _read(w: Any, info: dict[str, Any]) -> Any:
        kind = info.get("type")
        if isinstance(w, _NumberControl):
            return w.value()
        if kind == "boolean":
            return w.isChecked()
        if kind == "color":
            return w.value
        if kind == "enum":
            return w.currentData()
        if kind in ("number", "integer"):
            return w.value()
        return w.text()

    def current(self) -> dict[str, Any]:
        """Values that differ from the defaults."""
        out = {}
        for name, (w, info) in self.controls.items():
            v = self._read(w, info)
            if v != info.get("default"):
                out[name] = v
        return out

    def _changed(self, *_: Any) -> None:
        self.values = self.current()
        if self.live.isChecked():
            self._timer.start()

    def _emit(self) -> None:
        self._timer.stop()
        self.values = self.current()
        self.valuesChanged.emit(dict(self.values))

    def reset(self) -> None:
        self.values = {}
        self._build()
        self._emit()
