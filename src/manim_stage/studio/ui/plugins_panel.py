"""Plugins tab: Studio plugins (loaded / disabled with the reason) and Manim plugins."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class PluginsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Plugins")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(QLabel("<b>Studio plugins</b> (<code>manim_stage.plugins</code>)"))
        self.tree = QTreeWidget()
        self.tree.setAccessibleName("Studio plugins")
        self.tree.setHeaderLabels(["", "plugin", "hooks / reason", "from"])
        self.tree.setColumnWidth(0, 28)
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(2, 220)
        lay.addWidget(self.tree, 2)
        lay.addWidget(QLabel("<b>Manim plugins</b> (entry points <code>manim.plugins</code>)"))
        self.manim = QTreeWidget()
        self.manim.setAccessibleName("Manim plugins")
        self.manim.setHeaderLabels(["plugin"])
        lay.addWidget(self.manim, 1)

    def show(self, plugins: list[Any], manim_plugins: list[str]) -> None:  # type: ignore[override]
        self.tree.clear()
        for lp in plugins:
            detail = ", ".join(lp.hooks) if lp.enabled else lp.reason
            it = QTreeWidgetItem(["✔" if lp.enabled else "⚠", lp.name, detail, lp.source])
            it.setToolTip(2, "\n".join(lp.errors) or detail)
            self.tree.addTopLevelItem(it)
        if not plugins:
            self.tree.addTopLevelItem(QTreeWidgetItem(["", "(none installed)", "", ""]))
        self.manim.clear()
        for name in manim_plugins or ["(none installed)"]:
            self.manim.addTopLevelItem(QTreeWidgetItem([name]))
