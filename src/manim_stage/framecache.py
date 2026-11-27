"""Bounded on-disk cache of preview frames (ADR-0007, spec §9).

Layout: ``<root>/<revision>/<frame:06d>.png``. A *revision* identifies everything that
determines the pixels: scene file bytes, scene name, render settings, Manim version,
and (passed as ``extra`` by the runner) the content of every local module and asset the
scene used (:mod:`manim_stage.deps`).

LRU: reads touch a frame's mtime; :meth:`FrameCache.trim` deletes least recently
used frames until the cache fits ``budget_bytes``. Writes are atomic, so a reader never
sees a partial PNG and an interrupted runner leaves no corrupt frames.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

_REV_RE = re.compile(r"^[0-9a-f]{16,64}$")


def revision_key(
    scene_file: str | os.PathLike[str],
    scene: str,
    settings: Mapping[str, Any],
    *,
    manim_version: str = "",
    extra: Iterable[bytes] = (),
) -> str:
    h = hashlib.sha256()
    h.update(Path(scene_file).read_bytes())
    h.update(b"\0" + scene.encode())
    h.update(b"\0" + json.dumps(dict(settings), sort_keys=True, default=str).encode())
    h.update(b"\0" + manim_version.encode())
    for blob in extra:
        h.update(b"\0" + blob)
    return h.hexdigest()[:32]


class FrameCache:
    def __init__(self, root: str | os.PathLike[str], budget_bytes: int = 2 * 1024**3) -> None:
        self.root = Path(root)
        self.budget_bytes = budget_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, revision: str) -> Path:
        if not _REV_RE.match(revision):  # also blocks path traversal via revision ids
            raise ValueError(f"invalid revision id {revision!r}")
        return self.root / revision

    def path(self, revision: str, frame: int) -> Path:
        if frame < 0:
            raise ValueError("frame index must be >= 0")
        return self._dir(revision) / f"{int(frame):06d}.png"

    def put(self, revision: str, frame: int, image: Any, *, compress_level: int = 1) -> Path:
        """Store a PIL image atomically. Low PNG compression keeps writes fast."""
        target = self.path(revision, frame)
        for attempt in range(5):
            # A concurrent trim() may remove the (still empty) revision folder between
            # mkdir and mkstemp; once our temp file exists the folder is not empty.
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".png")
                break
            except FileNotFoundError:
                if attempt == 4:
                    raise
        try:
            with os.fdopen(fd, "wb") as f:
                image.save(f, format="PNG", compress_level=compress_level)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return target

    def get(self, revision: str, frame: int) -> Path | None:
        p = self.path(revision, frame)
        try:
            os.utime(p)
        except FileNotFoundError:
            return None
        return p

    def frames(self, revision: str) -> list[int]:
        d = self._dir(revision)
        if not d.is_dir():
            return []
        return sorted(int(p.stem) for p in d.glob("[0-9]*.png"))

    def _entries(self) -> list[tuple[Path, os.stat_result]]:
        """Committed frames only (temp files start with '.'), tolerating frames that
        another process renames or evicts while we look."""
        out = []
        for d in self.root.iterdir():
            if not (d.is_dir() and _REV_RE.match(d.name)):
                continue
            for p in d.glob("[0-9]*.png"):
                with contextlib.suppress(FileNotFoundError):
                    out.append((p, p.stat()))
        return out

    def size_bytes(self) -> int:
        return sum(st.st_size for _, st in self._entries())

    def trim(self, keep: str | None = None) -> int:
        """Evict least recently used frames until within budget; never evicts ``keep``'s
        frames unless that revision alone exceeds the budget. Returns bytes freed.
        Safe to run while other runners write to the cache."""
        entries = [(p.parent.name == keep, st.st_mtime, st.st_size, p) for p, st in self._entries()]
        total = sum(e[2] for e in entries)
        freed = 0
        for _protected, _mtime, size, p in sorted(entries, key=lambda e: (e[0], e[1])):
            if total - freed <= self.budget_bytes:
                break
            p.unlink(missing_ok=True)
            freed += size
        for d in self.root.iterdir():
            if d.is_dir() and _REV_RE.match(d.name):
                with contextlib.suppress(OSError):  # not empty, or removed concurrently
                    if not any(d.iterdir()):
                        d.rmdir()
        return freed
