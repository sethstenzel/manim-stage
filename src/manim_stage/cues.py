"""Named timing cues: sidecar store and resolver (spec F03, ADR-0006). No Manim import.

A *cue* is a named, adjustable ``wait``: ``self.cue("explain_swap", at=4.0)`` waits
until 4 s into the scene, unless ``.manim-stage/cues.json`` overrides the target
(edited by dragging on the Studio timeline, or by hand). Python stays the source of
truth for *order*; the sidecar only moves *when*.

Time model (docs/schemas/README.md): targets are absolute frame indices from scene
start, stored with the frame rate they were authored at, and rescaled to the render
frame rate with ``round(frame * r_new / r_old)``: accurate to one frame (spec §9).

One resolver (:class:`CueResolver`) is used by the Studio preview, ``manim render``
of a :class:`~manim_stage.scene.StageScene`, and ``manim-stage bake/validate``.

Errors (raise :class:`CueError`, failing the render):
  - a target before the time the cue is reached (it would need a negative wait);
  - the same cue name twice in one scene run.
Warnings (reported, render continues):
  - sidecar overrides for cues the scene no longer reaches (orphans; kept as
    tombstones until dismissed).
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "manim_stage.cues"
VERSION = 1
SIDECAR_DIR = ".manim-stage"
SIDECAR_NAME = "cues.json"
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_EPS = 1e-9


class CueError(ValueError):
    """An invalid cue (bad name, duplicate, negative wait). ``file``/``line`` point at it."""

    def __init__(self, message: str, *, file: str | None = None, line: int | None = None):
        super().__init__(message)
        self.file, self.line = file, line


# -- time helpers ----------------------------------------------------------------------


def frames_for_duration(seconds: float, fps: float) -> int:
    """Frames a ``wait(seconds)`` advances (Manim's frame-quantized clock: ceil)."""
    return max(0, math.ceil(seconds * fps - _EPS))


def frame_at(seconds: float, fps: float) -> int:
    """Nearest frame to an absolute time (cue ``at=``)."""
    return max(0, math.floor(seconds * fps + 0.5))


def rescale(frame: int, from_fps: float, to_fps: float) -> int:
    if from_fps == to_fps:
        return frame
    return max(0, math.floor(frame * to_fps / from_fps + 0.5))


# -- project / sidecar -----------------------------------------------------------------


def project_root(scene_file: str | os.PathLike[str]) -> Path:
    """Nearest folder at or above the scene file that has ``.manim-stage/``; else its folder."""
    start = Path(scene_file).resolve().parent
    for d in (start, *start.parents):
        if (d / SIDECAR_DIR).is_dir():
            return d
    return start


def sidecar_path(scene_file: str | os.PathLike[str]) -> Path:
    return project_root(scene_file) / SIDECAR_DIR / SIDECAR_NAME


@dataclass
class CueOverride:
    target_frame: int
    description: str | None = None
    audio_segment: str | None = None
    tombstone: bool = False
    updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"target_frame": int(self.target_frame)}
        for k in ("description", "audio_segment", "updated"):
            if getattr(self, k):
                d[k] = getattr(self, k)
        if self.tombstone:
            d["tombstone"] = True
        return d


@dataclass
class CueFile:
    """In-memory ``cues.json``. ``scenes[scene][cue] -> CueOverride``."""

    frame_rate: float = 30.0
    scenes: dict[str, dict[str, CueOverride]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "frame_rate": self.frame_rate,
            "scenes": {
                s: {"cues": {n: c.to_dict() for n, c in sorted(cues.items())}}
                for s, cues in sorted(self.scenes.items())
                if cues
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CueFile:
        if d.get("schema") != SCHEMA:
            raise CueError(f"not a cues file (schema {d.get('schema')!r})")
        if d.get("version") != VERSION:
            raise CueError(f"unsupported cues.json version {d.get('version')!r}")
        out = cls(frame_rate=float(d["frame_rate"]))
        for scene, body in d.get("scenes", {}).items():
            out.scenes[scene] = {
                name: CueOverride(
                    target_frame=int(c["target_frame"]),
                    description=c.get("description"),
                    audio_segment=c.get("audio_segment"),
                    tombstone=bool(c.get("tombstone", False)),
                    updated=c.get("updated"),
                )
                for name, c in body.get("cues", {}).items()
            }
        return out

    def target_seconds(self, scene: str, name: str) -> float | None:
        c = self.scenes.get(scene, {}).get(name)
        if c is None or c.tombstone:
            return None
        return c.target_frame / self.frame_rate

    def set_target(self, scene: str, name: str, seconds: float, **extra: Any) -> None:
        if not NAME_RE.match(name):
            raise CueError(f"invalid cue name {name!r}")
        cue = self.scenes.setdefault(scene, {}).get(name)
        frame = frame_at(seconds, self.frame_rate)
        now = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()
        if cue is None:
            self.scenes[scene][name] = CueOverride(frame, updated=now, **extra)
        else:
            cue.target_frame, cue.tombstone, cue.updated = frame, False, now
            for k, v in extra.items():
                setattr(cue, k, v)

    def remove(self, scene: str, name: str) -> None:
        self.scenes.get(scene, {}).pop(name, None)


def load(path: str | os.PathLike[str]) -> CueFile:
    """Read a sidecar. Missing file: empty. Corrupt file: falls back to the ``.bak``
    copy if there is one, else raises :class:`CueError` (never silently drops cues)."""
    path = Path(path)
    if not path.exists():
        return CueFile()
    try:
        return CueFile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            with contextlib.suppress(Exception):
                return CueFile.from_dict(json.loads(bak.read_text(encoding="utf-8")))
        raise CueError(f"{path} is corrupt ({exc}); fix it or delete it") from exc


def save(path: str | os.PathLike[str], cues: CueFile) -> Path:
    """Write atomically (temp file + rename) and keep the previous version as ``.bak``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cues.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".cues-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


# -- resolver --------------------------------------------------------------------------


@dataclass
class CueRecord:
    """What happened to one cue in one scene run (reported to the timeline)."""

    name: str
    call_frame: int
    target_frame: int
    default_frame: int
    overridden: bool
    description: str | None = None
    source: dict[str, Any] | None = None
    play_index: int | None = None  # the Manim play/wait that implemented the wait

    @property
    def wait_frames(self) -> int:
        return self.target_frame - self.call_frame

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "call_frame": self.call_frame,
            "target_frame": self.target_frame,
            "default_frame": self.default_frame,
            "overridden": self.overridden,
            "description": self.description,
            "source": self.source,
            "play_index": self.play_index,
        }


class CueResolver:
    """Resolves the cues of one scene run, at the render frame rate."""

    def __init__(self, scene: str, fps: float, overrides: CueFile | None = None) -> None:
        self.scene, self.fps = scene, float(fps)
        self.overrides = overrides or CueFile()
        self.records: list[CueRecord] = []

    def resolve(
        self,
        name: str,
        call_frame: int,
        *,
        at: float | None = None,
        after: float | None = None,
        description: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> CueRecord:
        where = {
            "file": source.get("path") if source else None,
            "line": source.get("line") if source else None,
        }
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise CueError(
                f"invalid cue name {name!r}: use 1-64 letters, digits, '_', '.', '-'", **where
            )
        if at is not None and after is not None:
            raise CueError(f"cue {name!r}: give at= or after=, not both", **where)
        if at is not None and at < 0 or after is not None and after < 0:
            raise CueError(f"cue {name!r}: times must be >= 0", **where)
        if any(r.name == name for r in self.records):
            raise CueError(
                f"cue {name!r} is reached twice in scene {self.scene}; cue names must be "
                "unique per scene (in a loop, use e.g. cue(f'step_{i}'))",
                **where,
            )
        if at is not None:
            default = frame_at(at, self.fps)
        elif after is not None:
            default = call_frame + frames_for_duration(after, self.fps)
        else:
            default = call_frame
        override = self.overrides.scenes.get(self.scene, {}).get(name)
        overridden = override is not None and not override.tombstone
        target = (
            rescale(override.target_frame, self.overrides.frame_rate, self.fps)
            if overridden
            else default
        )
        if target < call_frame:
            what = "its sidecar override" if overridden else "its default"
            raise CueError(
                f"cue {name!r} targets {target / self.fps:.3f} s ({what}) but the scene is "
                f"already at {call_frame / self.fps:.3f} s when it is reached: that would be a "
                "negative wait. Move the cue later, or earlier code/cues sooner.",
                **where,
            )
        rec = CueRecord(name, call_frame, target, default, overridden, description, source)
        self.records.append(rec)
        return rec

    def orphans(self) -> list[str]:
        """Sidecar overrides for this scene that no cue reached."""
        reached = {r.name for r in self.records}
        cues = self.overrides.scenes.get(self.scene, {})
        return sorted(n for n, c in cues.items() if n not in reached and not c.tombstone)


def check_monotonic(records: Iterable[CueRecord]) -> list[str]:
    """Targets must not decrease in call order (guaranteed at run time; re-checked for
    edited sidecars by ``validate``)."""
    problems, last = [], None
    for r in records:
        if last is not None and r.target_frame < last.target_frame:
            problems.append(f"cue {r.name!r} is before {last.name!r} but reached after it")
        last = r
    return problems
