"""Timeline layout: events → lanes and rows; ruler ticks (spec F02). No Qt.

Lanes, top to bottom (Manim terms, ADR-0013):

- **Sections** — ``next_section`` markers (zero-length).
- **Cues** — ``self.cue(...)`` targets of a StageScene (zero-length, draggable in 2.2).
- **Animations** — one bar per ``play`` / ``wait`` call.
- **Level 1, 2, …** — members of ``AnimationGroup`` / ``LaggedStart`` / ``Succession``
  (and nested groups), one lane per nesting depth.
- **Audio** — ``add_sound`` clips.
- **Captions** — subcaptions, if any.

Members of a group often overlap in time (that is the point of ``AnimationGroup``), so
each lane packs its events into as many rows as needed: an event goes into the first
row whose last event has ended (greedy interval partitioning, which is optimal).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EventBox:
    id: str
    kind: str
    label: str
    start: int
    end: int  # exclusive; == start for markers
    meta: dict[str, Any]
    source: dict[str, Any] | None
    parent_id: str | None
    depth: int = 0

    @property
    def is_marker(self) -> bool:
        return self.end <= self.start

    @property
    def animation(self) -> dict[str, Any] | None:
        """Manim animation info (MF.2): own for members, single animation for plays."""
        if "animation" in self.meta:
            return self.meta["animation"]
        anims = self.meta.get("animations") or []
        return anims[0] if len(anims) == 1 else None

    @property
    def category(self) -> str:
        if self.kind == "wait":
            return "wait"
        if self.kind in ("section", "sound", "caption", "cue", "plugin"):
            return self.kind
        anim = self.animation
        if anim:
            return anim.get("category", "animation")
        anims = self.meta.get("animations") or []
        return "composition" if len(anims) > 1 else "animation"


@dataclass
class Lane:
    key: str
    title: str
    rows: list[list[EventBox]] = field(default_factory=list)

    def add(self, box: EventBox) -> None:
        for row in self.rows:
            last = row[-1]
            if box.start >= max(last.end, last.start + (1 if last.is_marker else 0)):
                row.append(box)
                return
        self.rows.append([box])


@dataclass
class Layout:
    lanes: list[Lane]
    total: int
    fps: float
    by_id: dict[str, EventBox]

    @property
    def row_count(self) -> int:
        return sum(max(1, len(lane.rows)) for lane in self.lanes)

    def ordered(self) -> list[EventBox]:
        """Events in reading order (by start, then lane), for keyboard navigation."""
        order = {lane.key: i for i, lane in enumerate(self.lanes)}
        boxes = [b for lane in self.lanes for row in lane.rows for b in row]
        return sorted(boxes, key=lambda b: (b.start, order[lane_key(b)], b.id))

    def at(self, frame: int, lane_key_: str) -> list[EventBox]:
        lane = next((ln for ln in self.lanes if ln.key == lane_key_), None)
        if lane is None:
            return []
        return [b for row in lane.rows for b in row if b.start <= frame < max(b.end, b.start + 1)]


def lane_key(box: EventBox) -> str:
    if box.kind == "section":
        return "sections"
    if box.kind == "cue":
        return "cues"
    if box.kind == "plugin":
        return box.meta.get("_track", "plugin")
    if box.kind == "sound":
        return "audio"
    if box.kind == "caption":
        return "captions"
    return "main" if box.depth == 0 else f"level{box.depth}"


def build_layout(timeline: dict[str, Any]) -> Layout:
    """Lay out a SceneTimeline dict (``docs/schemas/timeline.schema.json``)."""
    boxes: list[EventBox] = []
    for e in timeline.get("events", []):
        track = e.get("track", "main")
        depth = int(track.split("/")[1]) if track.startswith("main/") else 0
        boxes.append(
            EventBox(
                id=e["id"],
                kind=e["kind"],
                label=e.get("label", ""),
                start=int(e["start_frame"]),
                end=int(e["end_frame"]),
                meta=e.get("meta") or {},
                source=e.get("source"),
                parent_id=e.get("parent_id"),
                depth=depth,
            )
        )
        if e["kind"] == "plugin":
            boxes[-1].meta = {**boxes[-1].meta, "_track": track}
    max_depth = max((b.depth for b in boxes), default=0)
    lanes = [Lane("sections", "Sections"), Lane("cues", "Cues"), Lane("main", "Animations")]
    lanes += [Lane(f"level{d}", f"Level {d}") for d in range(1, max_depth + 1)]
    lanes += [Lane("audio", "Audio"), Lane("captions", "Captions")]
    for e in timeline.get("events", []):  # one lane per plugin track (Studio plugins, F11)
        track = e.get("track", "")
        if e.get("kind") == "plugin" and all(ln.key != track for ln in lanes):
            lanes.append(Lane(track, track.split(":", 1)[-1].capitalize()))
    by_key = {lane.key: lane for lane in lanes}
    for box in sorted(boxes, key=lambda b: (b.start, b.end, b.id)):
        by_key[lane_key(box)].add(box)
    keep = [ln for ln in lanes if ln.rows or ln.key in ("main", "sections")]
    return Layout(
        keep,
        int(timeline.get("duration_frames", 0)),
        float(timeline.get("frame_rate", 15.0)),
        {b.id: b for b in boxes},
    )


# -- ruler -----------------------------------------------------------------------------

_STEPS_S = (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600)


@dataclass(frozen=True)
class Tick:
    frame: float
    major: bool
    label: str


def ruler_ticks(
    fps: float, px_per_frame: float, first: float, last: float, min_label_px: float = 70
) -> list[Tick]:
    """Ticks for frames ``first..last``. Labels in seconds; frame-level ticks when zoomed in.

    When a single frame is wider than ``min_label_px``/4, every frame gets a minor tick
    and seconds get major labelled ticks; otherwise major ticks are the smallest
    "nice" seconds step whose labels don't collide.
    """
    if fps <= 0 or px_per_frame <= 0:
        return []
    px_per_s = px_per_frame * fps
    step = next((s for s in _STEPS_S if s * px_per_s >= min_label_px), _STEPS_S[-1])
    ticks: list[Tick] = []
    k0 = math.floor(first / fps / step)
    k1 = math.ceil(last / fps / step)
    for k in range(k0, k1 + 1):
        secs = k * step
        f = secs * fps
        if first - 1 <= f <= last + 1:
            ticks.append(Tick(f, True, format_seconds(secs)))
    minor_frames = px_per_frame >= min_label_px / 8
    if minor_frames:
        for f in range(max(0, math.floor(first)), math.ceil(last) + 1):
            if not any(abs(t.frame - f) < 1e-6 for t in ticks):
                ticks.append(Tick(float(f), False, ""))
    else:
        sub = step / 5
        k0, k1 = math.floor(first / fps / sub), math.ceil(last / fps / sub)
        for k in range(k0, k1 + 1):
            if k % 5:
                ticks.append(Tick(k * sub * fps, False, ""))
    return sorted(ticks, key=lambda t: t.frame)


def format_seconds(secs: float) -> str:
    if secs >= 60:
        m, s = divmod(secs, 60)
        return f"{int(m)}:{s:04.1f}" if s % 1 else f"{int(m)}:{int(s):02d}"
    return f"{secs:g}s"


def resolve_source(path: str, scene_file: Path) -> Path:
    """Manim records call sites relative to the scene's folder; make them absolute."""
    p = Path(path)
    if p.is_absolute() and p.exists():
        return p
    for cand in (scene_file.parent / p, scene_file.parent / p.name):
        if cand.exists():
            return cand
    return scene_file
