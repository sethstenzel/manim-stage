"""Scene events: the timeline contract between the runner and the editor (ADR-0005).

Times are integer frame indices at the scene's frame rate. Ranges are half-open:
an event with ``start_frame=3, end_frame=5`` covers frames 3 and 4. Markers that
take no time (sections) have ``end_frame == start_frame``. Seconds are derived
(``frame / frame_rate``) except for sounds, whose exact start can fall between
frames; it is kept in ``meta["start_seconds"]``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA_VERSION = 1

EventKind = Literal["play", "wait", "animation", "section", "sound", "caption"]


@dataclass(frozen=True)
class SourceRef:
    path: str
    line: int


@dataclass(frozen=True)
class SceneEvent:
    id: str
    """Stable across runs of the same source: ``scene:kind:path:line#occurrence``.
    Child animations append ``/index`` to their parent's id."""
    kind: EventKind
    scene: str
    start_frame: int
    end_frame: int
    track: str
    """Display lane: ``"main"`` for plays and waits, ``"sections"``, ``"audio"``,
    ``"captions"``, or ``"main/<depth>"`` for nested animations."""
    label: str
    source: SourceRef | None = None
    parent_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SceneTimeline:
    scene: str
    frame_rate: float
    duration_frames: int
    events: tuple[SceneEvent, ...]
    source_sha256: str | None = None
    warnings: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def seconds(self, frame: int) -> float:
        return frame / self.frame_rate

    def by_id(self) -> dict[str, SceneEvent]:
        return {e.id: e for e in self.events}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "manim_stage.timeline",
            "version": self.schema_version,
            "scene": self.scene,
            "frame_rate": self.frame_rate,
            "duration_frames": self.duration_frames,
            "source_sha256": self.source_sha256,
            "warnings": list(self.warnings),
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneTimeline:
        if data.get("schema") != "manim_stage.timeline":
            raise ValueError("not a manim_stage timeline")
        if data.get("version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported timeline version {data.get('version')}")
        events = tuple(
            SceneEvent(
                **{k: v for k, v in e.items() if k != "source"},
                source=SourceRef(**e["source"]) if e.get("source") else None,
            )
            for e in data["events"]
        )
        return cls(
            scene=data["scene"],
            frame_rate=data["frame_rate"],
            duration_frames=data["duration_frames"],
            events=events,
            source_sha256=data.get("source_sha256"),
            warnings=tuple(data.get("warnings", ())),
        )
