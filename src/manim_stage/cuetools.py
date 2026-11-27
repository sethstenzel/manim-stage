"""``manim-stage validate`` / ``bake`` for named cues (spec F03, ADR-0006).

Both run each StageScene's timeline pass in a runner child (the same resolver the
preview and ``manim render`` use) at the sidecar's frame rate, so reported frames are
exactly what the sidecar stores.

- **validate** reports, per scene: every cue (call time, default, target, override),
  errors (duplicate names, negative waits, invalid names → the scene fails) and
  warnings (orphaned overrides). Exit status 1 on any error.
- **bake** writes every reached cue's resolved target into ``cues.json`` (defaults
  become explicit overrides), keeps descriptions, and marks orphans as tombstones.
  A baked sidecar pins timing even if ``at=``/``after=`` defaults later change.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import cues as cue_store
from .runner import RunnerError, child_env, run_capture, runner_command


@dataclass
class SceneCues:
    scene: str
    fps: float
    cues: list[dict[str, Any]] = field(default_factory=list)  # timeline cue events' meta
    orphans: list[str] = field(default_factory=list)
    error: str | None = None
    error_location: str | None = None


def stage_scenes(file: Path) -> list[str]:
    """Names of StageScene / StageMixin scenes in the file."""
    proc = subprocess.run(
        runner_command(file, None, list_scenes=True),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env(),
        cwd=file.parent,
    )
    for raw in proc.stdout.splitlines():
        try:
            m = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if m.get("type") == "scenes":
            return [s["name"] for s in m["scenes"] if s.get("stage")]
        if m.get("type") == "error":
            raise RunnerError(m["message"], file=m.get("file"), line=m.get("line"))
    raise RunnerError(f"could not list scenes in {file}", tb=proc.stderr)


def collect(file: str | Path, scenes: list[str] | None = None) -> list[SceneCues]:
    file = Path(file).resolve()
    sidecar = cue_store.load(cue_store.sidecar_path(file))
    fps = sidecar.frame_rate
    out = []
    for scene in scenes or stage_scenes(file):
        rep = SceneCues(scene, fps)
        try:
            tl = run_capture(file, scene, fps=fps, width=64, height=36).timeline
        except RunnerError as e:
            rep.error = str(e)
            rep.error_location = f"{Path(e.file).name}:{e.line}" if e.file and e.line else None
        else:
            rep.cues = [e.meta for e in tl.events if e.kind == "cue"]
            rep.orphans = sorted(
                w.split("'")[1] for w in tl.warnings if w.startswith("cue '") and "orphan" in w
            )
        out.append(rep)
    return out


def format_report(reports: list[SceneCues]) -> str:
    lines = []
    for r in reports:
        lines.append(f"{r.scene}:")
        if r.error:
            where = f" ({r.error_location})" if r.error_location else ""
            lines.append(f"  ERROR {r.error}{where}")
            continue
        if not r.cues:
            lines.append("  (no cues)")
        for c in r.cues:
            src = "override" if c["overridden"] else "default"
            lines.append(
                f"  {c['name']:24s} reached {c['call_frame'] / r.fps:7.3f}s  "
                f"target {c['target_frame'] / r.fps:7.3f}s ({src}; default "
                f"{c['default_frame'] / r.fps:.3f}s)  waits {c['wait_frames'] / r.fps:.3f}s"
            )
        for o in r.orphans:
            lines.append(f"  WARN  {o!r} is in cues.json but no longer reached (orphan)")
    return "\n".join(lines)


def bake(file: str | Path, scenes: list[str] | None = None) -> tuple[Path, list[SceneCues]]:
    """Write resolved targets to the sidecar. Raises CueError if any scene fails."""
    file = Path(file).resolve()
    path = cue_store.sidecar_path(file)
    if not path.parent.exists():
        path = file.parent / cue_store.SIDECAR_DIR / cue_store.SIDECAR_NAME
    reports = collect(file, scenes)
    failed = [r for r in reports if r.error]
    if failed:
        raise cue_store.CueError(
            "; ".join(f"{r.scene}: {r.error}" for r in failed) + " (nothing written)"
        )
    data = cue_store.load(path)
    for r in reports:
        existing = data.scenes.setdefault(r.scene, {})
        for c in r.cues:
            prev = existing.get(c["name"])
            seconds = c["target_frame"] / r.fps
            desc = (prev.description if prev else None) or c.get("description")
            data.set_target(r.scene, c["name"], seconds, description=desc)
        for name in r.orphans:
            existing[name].tombstone = True
    cue_store.save(path, data)
    return path, reports
