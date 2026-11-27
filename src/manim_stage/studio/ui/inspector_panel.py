"""Inspector: the scene's Mobject tree at the playhead, and editing of exposed
properties (spec F08, MF.5).

Every Mobject is shown read-only (class, name, bounds, colours, opacity, z-index,
updaters). Objects a scene opted in with ``self.expose(...)`` get editors for the
declared properties: **Preview** re-renders with the change (nothing saved),
**Save** writes ``.manim-stage/properties.json`` (undoable), **Discard** drops the
preview, **Copy as Python** puts the equivalent Manim calls on the clipboard.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .project_panel import ColorButton


class InspectorPanel(QWidget):
    inspectRequested = Signal()
    nodeSelected = Signal(object)  # node dict or None
    previewRequested = Signal(str, object)  # exposed name, props
    saveRequested = Signal(str, object)
    discardRequested = Signal()
    copyRequested = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Inspector")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        bar = QHBoxLayout()
        self.inspect_btn = QPushButton("Inspect frame")
        self.inspect_btn.setAccessibleName("Inspect the scene at the playhead")
        self.inspect_btn.setToolTip("Read the Mobject tree at the playhead (Ctrl+I)")
        self.auto = QCheckBox("Follow playhead")
        self.auto.setAccessibleName("Re-inspect when the playhead stops")
        bar.addWidget(self.inspect_btn)
        bar.addWidget(self.auto)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.status = QLabel("Press Inspect frame, then click an object in the viewport.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Mobject tree")
        self.tree.setHeaderLabels(["Mobject", "z", "fill", "opacity"])
        self.tree.setColumnWidth(0, 200)
        split.addWidget(self.tree)
        self.props_host = QWidget()
        self.props = QFormLayout(self.props_host)
        split.addWidget(self.props_host)
        lay.addWidget(split, 1)
        self.inspect_btn.clicked.connect(self.inspectRequested)
        self.tree.currentItemChanged.connect(self._item_changed)
        self.items: dict[str, QTreeWidgetItem] = {}
        self.node: dict[str, Any] | None = None
        self.editors: dict[str, Any] = {}

    # -- tree -------------------------------------------------------------------------

    def set_tree(self, msg: dict[str, Any]) -> None:
        keep = self.node["id"] if self.node else None
        self.tree.clear()
        self.items = {}

        def add(parent: Any, n: dict[str, Any]) -> None:
            label = n["class"] + (f" “{n['name']}”" if n.get("name") else "")
            if n.get("exposed"):
                label += "  ✎"
            it = QTreeWidgetItem(
                [
                    label,
                    str(n.get("z_index", 0)),
                    n.get("fill_color") or "",
                    f"{n.get('fill_opacity', '')}",
                ]
            )
            it.setData(0, Qt.ItemDataRole.UserRole, n)
            it.setToolTip(0, f"{n['module']}.{n['class']} · id {n['id']}")
            (parent.addChild if isinstance(parent, QTreeWidgetItem) else self.tree.addTopLevelItem)(
                it
            )
            self.items[n["id"]] = it
            for c in n.get("children", []):
                add(it, c)

        for n in msg.get("tree", []):
            add(self.tree, n)
        self.status.setText(
            f"Frame {msg.get('frame', 0)}: {len(self.items)} mobjects. "
            "Click one in the viewport or below. ✎ = editable (expose())."
        )
        if keep in self.items:
            self.select(keep)

    def select(self, node_id: str | None) -> None:
        it = self.items.get(node_id) if node_id else None
        self.tree.setCurrentItem(it)
        if it is not None:
            self.tree.scrollToItem(it)

    def _item_changed(self, cur: QTreeWidgetItem | None, _prev: Any) -> None:
        self.node = cur.data(0, Qt.ItemDataRole.UserRole) if cur else None
        self._show_props()
        self.nodeSelected.emit(self.node)

    # -- properties -------------------------------------------------------------------

    def _clear_props(self) -> None:
        while self.props.rowCount():
            self.props.removeRow(0)
        self.editors = {}

    def _show_props(self) -> None:
        self._clear_props()
        n = self.node
        if n is None:
            return
        info = [("Class", f"{n['class']} ({n['module']})"), ("ID", n["id"])]
        if n.get("bounds"):
            b = n["bounds"]
            info.append(("Bounds", f"x {b[0]:.2f}…{b[2]:.2f}, y {b[1]:.2f}…{b[3]:.2f}"))
            info.append(("Size", f"{b[2] - b[0]:.2f} × {b[3] - b[1]:.2f}"))
        for key in (
            "fill_color",
            "fill_opacity",
            "stroke_color",
            "stroke_width",
            "z_index",
            "updaters",
            "points",
        ):
            if key in n and n[key] is not None:
                info.append((key, str(n[key])))
        for k, v in info:
            lab = QLabel(v)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.props.addRow(k, lab)
        ex = n.get("exposed")
        if not ex:
            self.props.addRow(
                QLabel(
                    "<i>Read-only. Call self.expose(mobject, name, …) in the "
                    "scene to edit it here.</i>"
                )
            )
            return
        self.props.addRow(QLabel(f"<b>Editable: {ex['name']}</b>"))
        for key, spec in ex["props"].items():
            w = self._editor(key, spec["type"], spec["value"])
            self.editors[key] = (w, spec["type"])
            self.props.addRow(key, w)
        row = QHBoxLayout()
        for text, sig in (
            ("Preview", self.previewRequested),
            ("Save", self.saveRequested),
            ("Copy as Python", self.copyRequested),
        ):
            b = QPushButton(text)
            b.setAccessibleName(f"{text} property edits")
            b.clicked.connect(lambda _=False, s=sig: s.emit(ex["name"], self.values()))
            row.addWidget(b)
        d = QPushButton("Discard")
        d.setAccessibleName("Discard previewed edits")
        d.clicked.connect(self.discardRequested)
        row.addWidget(d)
        host = QWidget()
        host.setLayout(row)
        self.props.addRow(host)

    def add_rows(self, title: str, rows: list[tuple[str, str]]) -> None:
        """Extra read-only rows, e.g. from Studio plugins."""
        if not rows:
            return
        self.props.addRow(QLabel(f"<b>{title}</b>"))
        for k, v in rows:
            self.props.addRow(str(k), QLabel(str(v)))

    def _editor(self, key: str, kind: str, value: Any) -> QWidget:
        if kind == "color":
            w: Any = ColorButton(str(value), f"Property {key}")
        elif kind == "integer":
            w = QSpinBox()
            w.setRange(-1000, 1000)
            w.setValue(int(value))
        elif kind == "point":
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            w.spins = []
            for v in value:
                s = QDoubleSpinBox()
                s.setRange(-100, 100)
                s.setDecimals(3)
                s.setValue(float(v))
                h.addWidget(s)
                w.spins.append(s)
        else:
            w = QDoubleSpinBox()
            w.setRange(-1000, 1000)
            w.setDecimals(3)
            w.setSingleStep(0.1)
            w.setValue(float(value))
        w.setAccessibleName(f"Property {key}")
        return w

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, (w, kind) in self.editors.items():
            if kind == "color":
                out[key] = w.value
            elif kind == "point":
                out[key] = [round(s.value(), 4) for s in w.spins]
            elif kind == "integer":
                out[key] = w.value()
            else:
                out[key] = round(w.value(), 4)
        return out
