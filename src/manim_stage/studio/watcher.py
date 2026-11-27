"""Polling file watcher with debounce (spec F01, §9: 200–500 ms).

Polls ``stat()`` of a small, changing set of files (the scene file and its
dependencies) instead of using OS notification APIs: no extra dependency, identical
behaviour on Windows, Linux and macOS, and editors that save by "write temp file and
rename" are handled because the watcher compares (mtime_ns, size), not handles.

A burst of saves within ``debounce`` seconds produces one callback, after the files
have been quiet for ``debounce`` seconds.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path

Signature = tuple[int, int] | None


def _signature(path: Path) -> Signature:
    try:
        st = os.stat(path)
    except OSError:
        return None  # missing (e.g. mid-rename) counts as a state too
    return (st.st_mtime_ns, st.st_size)


class FileWatcher:
    def __init__(
        self,
        paths: Callable[[], Iterable[Path]],
        on_change: Callable[[list[Path]], None],
        *,
        interval: float = 0.1,
        debounce: float = 0.3,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """``paths`` is called on every poll, so the watched set can change."""
        if not 0.05 <= debounce <= 5:
            raise ValueError("debounce must be between 0.05 and 5 seconds")
        self._paths, self._on_change, self._clock = paths, on_change, clock
        self.interval, self.debounce = interval, debounce
        self._known: dict[Path, Signature] = {}
        self._pending: set[Path] = set()
        self._last_change = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> FileWatcher:
        self._snapshot()
        self._thread = threading.Thread(target=self._run, name="manim-stage-watch", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _snapshot(self) -> None:
        self._known = {p: _signature(p) for p in self._current_paths()}

    def _current_paths(self) -> list[Path]:
        return sorted({Path(p) for p in self._paths()})

    def poll(self) -> list[Path] | None:
        """One polling step; returns the changed files when a debounced change fires."""
        now = self._clock()
        paths = self._current_paths()
        known = {}
        for p in paths:
            sig = _signature(p)
            if p in self._known and self._known[p] != sig:
                self._pending.add(p)
                self._last_change = now
            known[p] = sig  # newly watched paths are a baseline, not a change
        self._known = known
        if self._pending and now - self._last_change >= self.debounce:
            changed, self._pending = sorted(self._pending), set()
            return changed
        return None

    def acknowledge(self, paths: list[Path]) -> None:
        """Treat the current content of ``paths`` as already handled (e.g. the editor
        wrote them itself and re-rendered), so they don't trigger another change."""
        for p in paths:
            p = Path(p)
            self._known[p] = _signature(p)
            self._pending.discard(p)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                changed = self.poll()
            except Exception:  # never let the watcher thread die
                continue
            if changed:
                self._on_change(changed)
