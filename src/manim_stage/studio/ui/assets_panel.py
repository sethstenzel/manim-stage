"""Assets panel: what the scene file uses, whether it exists, and the machine's
capabilities (spec F10, MF.9).

- **Assets**: images, SVGs, sounds (code ``add_sound``/narration and audio-workspace
  clips) and fonts referenced by the scene file, resolved the way Manim resolves them;
  missing ones are marked ⚠. **Add asset…** copies a file into ``assets/<kind>/`` and
  puts the matching Manim call on the clipboard (``ImageMobject("assets/images/x.png")``).
- **Environment**: ``manim-stage doctor`` checks: Manim build, Cairo, Pango fonts, LaTeX
  for ``Tex``/``MathTex``, FFmpeg encoders per export format, Qt, preview audio, plugins.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

SNIPPETS = {
    "image": 'ImageMobject("{p}")',
    "svg": 'SVGMobject("{p}")',
    "audio": 'self.add_sound("{p}")',
    "video": '"{p}"  # video files: use as a narration/clip source or in compose',
    "font": 'Text("…", font="{name}")  # after installing/registering the font',
    "data": 'Path("{p}").read_text()',
}
FOLDERS = {
    "image": "images",
    "svg": "svg",
    "audio": "audio",
    "video": "video",
    "font": "fonts",
    "data": "data",
    "other": "misc",
}


def import_asset(root: Path, source: Path) -> tuple[str, str]:
    """Copy ``source`` into ``root/assets/<kind>/``; returns (project-relative path, kind)."""
    from ...assets import kind_of

    kind = kind_of(source)
    dest_dir = root / "assets" / FOLDERS.get(kind, "misc")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    n = 1
    while dest.exists() and dest.read_bytes() != source.read_bytes():
        dest = dest_dir / f"{source.stem}-{n}{source.suffix}"
        n += 1
    if not dest.exists():
        shutil.copy2(source, dest)
    return dest.relative_to(root).as_posix(), kind


class AssetsPanel(QWidget):
    refreshRequested = Signal()
    addRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Assets and environment")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Check assets")
        self.refresh_btn.setAccessibleName("Check the scene's assets and the environment")
        self.add_btn = QPushButton("Add asset…")
        self.add_btn.setAccessibleName("Copy a file into the project's assets folder")
        row.addWidget(self.refresh_btn)
        row.addWidget(self.add_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.list = QTreeWidget()
        self.list.setAccessibleName("Assets used by the scene")
        self.list.setHeaderLabels(["", "kind", "asset", "used at", "size"])
        self.list.setColumnWidth(0, 28)
        self.list.setColumnWidth(2, 170)
        self.list.itemDoubleClicked.connect(self._reveal)
        lay.addWidget(self.list, 2)
        lay.addWidget(QLabel("<b>Environment</b>"))
        self.env = QTreeWidget()
        self.env.setAccessibleName("Environment checks")
        self.env.setHeaderLabels(["", "check", "detail"])
        self.env.setColumnWidth(0, 28)
        self.env.setColumnWidth(1, 150)
        lay.addWidget(self.env, 1)
        self.refresh_btn.clicked.connect(self.refreshRequested)
        self.add_btn.clicked.connect(self.addRequested)

    def show_inventory(self, inv: Any) -> None:
        self.list.clear()
        for r in inv.refs:
            mark = "…" if r.dynamic else ("✔" if r.ok else "⚠")
            size = f"{r.resolved.stat().st_size / 1024:.0f} KB" if r.resolved else ""
            it = QTreeWidgetItem([mark, r.kind, r.name, r.source, size])
            it.setToolTip(
                2,
                str(r.resolved)
                if r.resolved
                else ("computed at run time" if r.dynamic else "not found"),
            )
            it.setData(0, Qt.ItemDataRole.UserRole, str(r.resolved) if r.resolved else "")
            self.list.addTopLevelItem(it)
        for font, src in inv.fonts_missing:
            self.list.addTopLevelItem(QTreeWidgetItem(["⚠", "font", font, src, "not installed"]))
        missing = len(inv.missing) + len(inv.fonts_missing)
        self.summary.setText(
            f"{len(inv.refs)} asset reference(s); "
            + (f"⚠ {missing} missing: the render will fail" if missing else "all found")
        )

    def show_environment(self, checks: list[Any]) -> None:
        self.env.clear()
        for c in checks:
            mark = {"ok": "✔", "warn": "!", "fail": "⚠"}[c.status]
            it = QTreeWidgetItem([mark, c.name, c.detail])
            it.setToolTip(2, c.detail)
            self.env.addTopLevelItem(it)

    def _reveal(self, item: QTreeWidgetItem, _col: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))
