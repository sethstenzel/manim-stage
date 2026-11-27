"""Which local files a scene depends on (ADR-0010: dependency-aware revisions).

A scene's pixels depend on more than its own file: helper modules it imports and
assets it loads (images, SVGs, sounds, data files). The runner records every file
Python opens for reading while importing and evaluating the scene, using an audit
hook (:pep:`578`), and keeps those that belong to the user's project:

- not inside the Python installation, a virtualenv or site-packages,
- not inside Manim's ``media_dir`` (Manim's own Text/SVG/LaTeX caches) or the frame cache.

Files opened from C code (e.g. by FFmpeg or Pango) are invisible to the hook; sound
files are added from the timeline's sound events instead. Fonts are system state and
are not tracked.

The content hash of every dependency is part of the frame-cache revision, so editing
a helper module or replacing an image invalidates cached frames.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import sys
import sysconfig
from collections.abc import Iterable
from pathlib import Path

_recorder: DependencyRecorder | None = None
_hook_installed = False


def _hook(event: str, args: tuple) -> None:
    rec = _recorder
    if rec is None or event != "open":
        return
    path, mode = args[0], args[1]
    if mode is not None and any(c in str(mode) for c in "wax+"):
        return
    if isinstance(path, (str, bytes, os.PathLike)) and not isinstance(path, int):
        rec._seen.add(os.fsdecode(path))


def _system_roots() -> list[Path]:
    roots = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix}
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        with contextlib.suppress(Exception):
            roots.add(sysconfig.get_path(key))
    roots.add(str(Path(__file__).resolve().parent))  # manim_stage itself
    return [Path(r).resolve() for r in roots if r]


class DependencyRecorder:
    """Context manager that records project files opened while it is active."""

    def __init__(self, exclude: Iterable[str | os.PathLike[str]] = ()) -> None:
        self._seen: set[str] = set()
        self._exclude = [Path(p).resolve() for p in exclude]

    def __enter__(self) -> DependencyRecorder:
        global _recorder, _hook_installed
        if not _hook_installed:  # audit hooks cannot be removed; install once
            sys.addaudithook(_hook)
            _hook_installed = True
        _recorder = self
        return self

    def __exit__(self, *exc: object) -> None:
        global _recorder
        _recorder = None

    def add(self, path: str | os.PathLike[str]) -> None:
        self._seen.add(os.fspath(path))

    def files(self) -> list[Path]:
        """Existing project files, resolved, sorted, without duplicates."""
        skip = _system_roots() + self._exclude
        out: set[Path] = set()
        for raw in self._seen:
            try:
                p = Path(raw).resolve()
            except (OSError, ValueError):
                continue
            if p.suffix == ".pyc" and p.parent.name == "__pycache__":
                # A cached import: Python read the bytecode, not the source.
                p = p.parent.parent / (p.name.split(".", 1)[0] + ".py")
            if not p.is_file() or any(p.is_relative_to(r) for r in skip):
                continue
            if "site-packages" in p.parts or "dist-packages" in p.parts:
                continue
            out.add(p)
        return sorted(out)


def content_hashes(files: Iterable[Path], root: Path) -> list[bytes]:
    """``relative-path\\0sha256`` per file; stable across machines for in-project files."""
    out = []
    for f in files:
        try:
            rel = f.relative_to(root).as_posix()
        except ValueError:
            rel = f.as_posix()
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        out.append(f"{rel}\0{digest}".encode())
    return out
