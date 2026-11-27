"""Guard against Qt bindings that corrupt refcounts when emitting signals.

PySide6 6.12.0 on Python 3.11/Linux drops a reference to None/True on every signal
emission; after a few thousand emissions the interpreter aborts ("none_dealloc").
If a dependency update brings such a build back, this fails fast with a clear message
instead of a random SIGABRT later in the suite.
"""

import sys

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402


class _Emitter(QObject):
    sig = Signal(object)


def _counts():
    return sys.getrefcount(None), sys.getrefcount(True), sys.getrefcount(False)


def test_signal_emission_keeps_singleton_refcounts(qapp: QApplication):
    e = _Emitter()
    e.sig.connect(lambda m: None)
    button = QToolButton()
    button.clicked.connect(lambda: None)
    before = _counts()
    for _ in range(200):
        e.sig.emit(1)
        button.click()
    after = _counts()
    lost = [b - a for a, b in zip(after, before, strict=True)]
    assert max(lost) < 50, (
        f"Qt bindings lose references to None/True/False on signal emission {lost}; "
        "this PySide6 build will crash the editor. See pyproject.toml [studio] pins."
    )
