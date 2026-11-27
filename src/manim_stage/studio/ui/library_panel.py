"""Library tab: a searchable catalog of Manim (and manim-stage) features (backlog MF.4).

Mobjects, animations, scene and camera types, rate functions (with their curve),
colours (with swatches), utilities and manim-stage APIs, grouped by Manim's own
module layout. Selecting an entry shows its signature and docs summary; **Copy Python**
(or a double-click) puts a ready snippet on the clipboard.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

KIND_LABELS = {
    "mobjects": "Mobjects",
    "animations": "Animations",
    "scenes": "Scene types",
    "cameras": "Cameras",
    "rate_functions": "Rate functions",
    "colors": "Colours",
    "manim_stage": "manim-stage",
    "utilities": "Utilities",
    "constants": "Constants",
    "modules": "Modules",
}
ROLE = Qt.ItemDataRole.UserRole


class CurveView(QWidget):
    """Draws a rate-function curve (samples of f(t), t in [0, 1])."""

    def __init__(self) -> None:
        super().__init__()
        self.samples: list[float] = []
        self.setMinimumHeight(90)
        self.setAccessibleName("Rate function curve")

    def set_samples(self, samples: list[float] | None) -> None:
        self.samples = list(samples or [])
        self.setVisible(bool(self.samples))
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 (Qt)
        if not self.samples:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        lo, hi = min(0.0, *self.samples), max(1.0, *self.samples)
        span = (hi - lo) or 1.0

        def pt(i: int, v: float) -> QPointF:
            x = r.left() + r.width() * i / (len(self.samples) - 1)
            return QPointF(x, r.bottom() - r.height() * (v - lo) / span)

        p.setPen(QPen(QColor("#555"), 1, Qt.PenStyle.DashLine))
        p.drawLine(pt(0, 0), pt(len(self.samples) - 1, 0))
        p.drawLine(pt(0, 1), pt(len(self.samples) - 1, 1))
        path = QPainterPath(pt(0, self.samples[0]))
        for i, v in enumerate(self.samples[1:], 1):
            path.lineTo(pt(i, v))
        p.setPen(QPen(QColor("#58c4dd"), 2))
        p.drawPath(path)
        p.end()


class LibraryPanel(QWidget):
    snippetCopied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Library")
        self.cat: dict[str, Any] | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.setMinimumWidth(0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Manim: Circle, fade, smooth, BLUE…")
        self.search.setAccessibleName("Search the library")
        self.search.setClearButtonEnabled(True)
        lay.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName("Library entries")
        split.addWidget(self.tree)
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 4, 0, 0)
        self.title = QLabel("")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.title.setWordWrap(True)
        dl.addWidget(self.title)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        dl.addWidget(self.summary)
        self.curve = CurveView()
        self.curve.setVisible(False)
        dl.addWidget(self.curve)
        self.snippet = QPlainTextEdit()
        self.snippet.setReadOnly(True)
        self.snippet.setAccessibleName("Python snippet")
        self.snippet.setMaximumHeight(80)
        dl.addWidget(self.snippet)
        row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy Python")
        self.copy_btn.setAccessibleName("Copy the snippet")
        self.docs_btn = QPushButton("Manim docs")
        self.docs_btn.setAccessibleName("Open the Manim reference page")
        row.addWidget(self.copy_btn)
        row.addWidget(self.docs_btn)
        row.addStretch(1)
        dl.addLayout(row)
        split.addWidget(detail)
        split.setSizes([400, 220])
        lay.addWidget(split, 1)
        self.count = QLabel("")
        self.count.setWordWrap(True)  # never let the status line widen the dock
        lay.addWidget(self.count)
        self.search.textChanged.connect(self._fill)
        self.tree.currentItemChanged.connect(lambda cur, _prev: self._show(cur))
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.copy())
        self.copy_btn.clicked.connect(self.copy)
        self.docs_btn.clicked.connect(self._open_docs)
        self._show(None)

    def load(self) -> None:
        """Build the catalog (first time the tab is shown; imports Manim once)."""
        if self.cat is None:
            from ... import catalog

            self.cat = catalog.catalog()
            self._fill(self.search.text())

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt)
        super().showEvent(event)
        self.load()

    def _fill(self, query: str = "") -> None:
        if self.cat is None:
            return
        from ... import catalog

        self.tree.clear()
        q = query.strip()
        entries = catalog.search(q, self.cat) if q else None
        n = 0
        for kind, label in KIND_LABELS.items():
            items = [
                e
                for e in (entries if entries is not None else self.cat["kinds"][kind])
                if e["kind"] == kind
            ]
            if not items:
                continue
            top = QTreeWidgetItem([f"{label} ({len(items)})"])
            self.tree.addTopLevelItem(top)
            groups: dict[str, QTreeWidgetItem] = {}
            for e in items:
                parent = top
                if kind in ("mobjects", "animations", "utilities", "manim_stage") and not q:
                    g = e.get("group", "")
                    if g not in groups:
                        groups[g] = QTreeWidgetItem([g])
                        top.addChild(groups[g])
                    parent = groups[g]
                it = QTreeWidgetItem([e["name"]])
                it.setData(0, ROLE, e)
                if "hex" in e:
                    it.setBackground(0, QColor(e["hex"]))
                    it.setForeground(
                        0, QColor("#000" if QColor(e["hex"]).lightness() > 128 else "#fff")
                    )
                parent.addChild(it)
                n += 1
            top.setExpanded(bool(q))
        self.count.setText(
            f"{n} entr{'y' if n == 1 else 'ies'} · Manim {self.cat['manim_version'].split('+')[0]}"
        )
        if q and n:
            first = self._first_leaf()
            if first:
                self.tree.setCurrentItem(first)

    def _first_leaf(self) -> QTreeWidgetItem | None:
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            stack = [top]
            while stack:
                it = stack.pop(0)
                if it.data(0, ROLE):
                    return it
                stack.extend(it.child(k) for k in range(it.childCount()))
        return None

    def current(self) -> dict[str, Any] | None:
        it = self.tree.currentItem()
        return it.data(0, ROLE) if it else None

    def _show(self, item: QTreeWidgetItem | None) -> None:
        e = item.data(0, ROLE) if item else None
        self.copy_btn.setEnabled(bool(e))
        self.docs_btn.setEnabled(bool(e and e.get("docs")))
        if not e:
            self.title.setText("<i>Pick an entry to see its signature and a snippet.</i>")
            self.summary.setText("")
            self.snippet.setPlainText("")
            self.curve.set_samples(None)
            return
        flags = []
        if e.get("needs_latex"):
            flags.append("needs LaTeX")
        if e.get("three_d"):
            flags.append("3D (ThreeDScene)")
        sig = e.get("signature", "")
        self.title.setText(
            f"<b>{e['name']}</b><code>{_esc(sig)}</code>"
            + (f"<br><small>{', '.join(flags)}</small>" if flags else "")
        )
        self.summary.setText(
            _esc(e.get("summary", "")) + f"<br><small>{e.get('module', '')}</small>"
        )
        self.snippet.setPlainText(e.get("snippet", ""))
        self.curve.set_samples(e.get("curve"))

    def copy(self) -> None:
        e = self.current()
        if not e:
            return
        QGuiApplication.clipboard().setText(e.get("snippet", e["name"]))
        self.snippetCopied.emit(e["name"])

    def _open_docs(self) -> None:
        e = self.current()
        if e and e.get("docs"):
            QDesktopServices.openUrl(QUrl(e["docs"]))


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
