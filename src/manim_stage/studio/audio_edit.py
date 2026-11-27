"""Editing audio-workspace clips from the Studio (spec F04, backlog 2.3b). No Qt.

Every change is an :class:`AudioEdit` holding the scene's whole clip list before and
after, so undo/redo is exact and one sidecar write per step. Imported files are
copied into the project (``assets/audio/``) so ``audio.json`` keeps portable,
project-relative paths (no absolute paths in metadata, spec §8).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import audio

MIN_LENGTH = 0.02  # seconds a clip can be trimmed down to
ASSETS = Path("assets") / "audio"


@dataclass
class AudioEdit:
    scene: str
    before: list[dict[str, Any]]
    after: list[dict[str, Any]]
    label: str

    def _write(self, sidecar: Path, clips: list[dict[str, Any]]) -> None:
        data = audio.load(sidecar)
        data.scenes[self.scene] = [audio.AudioClip.from_dict(c) for c in clips]
        audio.save(sidecar, data)

    def do(self, sidecar: Path) -> None:
        self._write(sidecar, self.after)

    def undo(self, sidecar: Path) -> None:
        self._write(sidecar, self.before)


def _clips(sidecar: Path, scene: str) -> list[dict[str, Any]]:
    return [c.to_dict() for c in audio.load(sidecar).scenes.get(scene, [])]


def project_relative(root: Path, file: Path) -> str:
    """Path of ``file`` inside the project, copying it into ``assets/audio/`` if needed."""
    file = file.resolve()
    root = root.resolve()
    if file.is_relative_to(root):
        return file.relative_to(root).as_posix()
    dest_dir = root / ASSETS
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file.name
    n = 1
    while dest.exists() and dest.read_bytes() != file.read_bytes():
        dest = dest_dir / f"{file.stem}-{n}{file.suffix}"
        n += 1
    if not dest.exists():
        shutil.copy2(file, dest)
    return dest.relative_to(root).as_posix()


def unique_id(existing: list[dict[str, Any]], stem: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_")[:56] or "clip"
    taken = {c["id"] for c in existing}
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def add_clip(sidecar: Path, root: Path, scene: str, source: Path, start: float) -> AudioEdit:
    before = _clips(sidecar, scene)
    rel = project_relative(root, source)
    clip = audio.AudioClip(unique_id(before, Path(rel).stem), rel, start=round(start, 4))
    return AudioEdit(scene, before, [*before, clip.to_dict()], f"Add audio {Path(rel).name}")


def change_clip(sidecar: Path, scene: str, clip_id: str, label: str, **changes: Any) -> AudioEdit:
    before = _clips(sidecar, scene)
    after = []
    for c in before:
        if c["id"] == clip_id:
            c = {**audio.AudioClip.from_dict(c).__dict__, **changes}
            c = audio.AudioClip(**c).to_dict()
        after.append(c)
    return AudioEdit(scene, before, after, label)


def remove_clip(sidecar: Path, scene: str, clip_id: str) -> AudioEdit:
    before = _clips(sidecar, scene)
    after = [c for c in before if c["id"] != clip_id]
    return AudioEdit(scene, before, after, f"Remove audio clip {clip_id!r}")


def drag_changes(
    clip: dict[str, Any], mode: str, delta: float, source_duration: float
) -> dict[str, Any]:
    """New ``start``/``trim_in``/``trim_out`` for a drag of ``delta`` seconds.

    - ``move``: shift the whole clip.
    - ``trim_in``: drag the left edge; the audio stays put in time (start and trim_in
      move together), clamped to the file's start and to the minimum length.
    - ``trim_out``: drag the right edge, clamped to the file's end.
    """
    start = float(clip.get("start", 0.0))
    t_in = float(clip.get("trim_in", 0.0))
    t_out = clip.get("trim_out")
    t_out = source_duration if t_out is None else float(t_out)
    if mode == "move":
        return {"start": round(start + delta, 4)}
    if mode == "trim_in":
        d = max(-t_in, min(delta, t_out - MIN_LENGTH - t_in))
        return {"start": round(start + d, 4), "trim_in": round(t_in + d, 4)}
    if mode == "trim_out":
        new_out = max(t_in + MIN_LENGTH, min(t_out + delta, source_duration))
        return {"trim_out": None if new_out >= source_duration else round(new_out, 4)}
    raise ValueError(f"unknown drag mode {mode!r}")


def source_duration(path: Path) -> float:
    """Length of an audio file in seconds (container metadata; decodes if missing)."""
    import av

    with av.open(str(path)) as c:
        s = c.streams.audio[0]
        if s.duration is not None and s.time_base is not None:
            return float(s.duration * s.time_base)
        if c.duration is not None:
            return c.duration / 1_000_000
    return audio.duration_of(path)


def muted_events(
    sidecar: Path, root: Path, scene: str, fps: float, present: set[str]
) -> list[dict[str, Any]]:
    """Timeline events for clips that aren't in the render (muted / not soloed), so they
    stay visible and editable."""
    import math

    data = audio.load(sidecar)
    active = {c.id for c in data.active(scene)}
    out = []
    for c in data.scenes.get(scene, []):
        if c.id in present:
            continue
        try:
            dur = source_duration(audio.resolve_file(c.file, root))
        except Exception:
            dur = 1.0
        length = (dur if c.trim_out is None else c.trim_out) - c.trim_in
        start = math.floor(c.start * fps + 1e-9)
        settings = {k: v for k, v in c.to_dict().items() if k != "id"}
        out.append(
            {
                "id": f"{scene}:sound:clip:{c.id}#0",
                "kind": "sound",
                "scene": scene,
                "start_frame": max(0, start),
                "end_frame": max(0, math.ceil((c.start + length) * fps)),
                "track": "audio",
                "label": c.label or Path(c.file).name,
                "source": None,
                "parent_id": None,
                "meta": {
                    "clip": c.id,
                    "clip_settings": settings,
                    "silent": True,
                    "silent_reason": "muted"
                    if c.mute
                    else ("not soloed" if c.id not in active else ""),
                },
            }
        )
    return out
