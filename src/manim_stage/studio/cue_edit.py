"""Moving cues on the timeline: planning, constraints, persistence, undo (spec F03, 2.2).

No Qt. The timeline calls :func:`plan_move` on every mouse move (to draw the preview)
and :func:`apply_targets` on drop; the undo stack stores the before/after targets.

Rules (ADR-0006):

- A cue can't be moved before the moment it is reached (``call_frame``): that would be
  a negative wait.
- **Hold** (default): other cues keep their absolute times. Moving a cue by Δ shifts
  everything up to the *next* cue by Δ, and the next cue's wait absorbs it. So Δ can't
  exceed the next cue's wait (it would become negative).
- **Ripple** (Shift while dragging): every later cue moves by Δ too, so the rest of the
  scene shifts as a block. There is no upper limit.

Frames here are at the *preview* frame rate; the sidecar stores its own rate and
:meth:`~manim_stage.cues.CueFile.set_target` converts via seconds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import cues as cue_store


@dataclass(frozen=True)
class CueInfo:
    """A cue as the last render resolved it (from the timeline's cue events)."""

    name: str
    call_frame: int
    target_frame: int
    default_frame: int
    overridden: bool

    @property
    def wait_frames(self) -> int:
        return self.target_frame - self.call_frame

    @classmethod
    def from_meta(cls, meta: dict[str, Any]) -> CueInfo:
        return cls(
            meta["name"],
            int(meta["call_frame"]),
            int(meta["target_frame"]),
            int(meta["default_frame"]),
            bool(meta.get("overridden")),
        )


@dataclass
class MovePlan:
    name: str
    requested: int
    target: int  # after clamping
    delta: int
    ripple: bool
    clamped: str | None = None  # why the target was limited, for the UI
    targets: dict[str, int] = field(default_factory=dict)  # cue -> new target frame
    shift_from: int = 0  # events starting in [shift_from, shift_until) move by delta
    shift_until: int | None = None  # None: to the end of the scene


def plan_move(cues: Sequence[CueInfo], name: str, frame: int, *, ripple: bool) -> MovePlan:
    """Where cue ``name`` and its neighbours end up if dropped at ``frame``."""
    order = list(cues)  # call order == time order
    i = next(k for k, c in enumerate(order) if c.name == name)
    cue = order[i]
    nxt = order[i + 1] if i + 1 < len(order) else None
    target, why = int(frame), None
    if target < cue.call_frame:
        target, why = cue.call_frame, "can't be earlier than where the cue is reached"
    if not ripple and nxt is not None and target - cue.target_frame > nxt.wait_frames:
        target = cue.target_frame + nxt.wait_frames
        why = f"would push past cue {nxt.name!r} (hold Shift to ripple)"
    delta = target - cue.target_frame
    plan = MovePlan(
        name, int(frame), target, delta, ripple, why, {name: target}, shift_from=cue.target_frame
    )
    if ripple:
        for later in order[i + 1 :]:
            plan.targets[later.name] = later.target_frame + delta
        plan.shift_until = None
    else:
        plan.shift_until = nxt.target_frame if nxt is not None else None
    return plan


def apply_targets(sidecar: Path, scene: str, seconds: dict[str, float | None]) -> None:
    """Set (seconds) or clear (None) overrides atomically, in one write."""
    data = cue_store.load(sidecar)
    for name, secs in seconds.items():
        if secs is None:
            data.remove(scene, name)
        else:
            data.set_target(scene, name, secs)
    cue_store.save(sidecar, data)


@dataclass
class CueEdit:
    """One undoable edit: the sidecar values before and after (seconds or None)."""

    scene: str
    before: dict[str, float | None]
    after: dict[str, float | None]
    label: str

    def do(self, sidecar: Path) -> None:
        apply_targets(sidecar, self.scene, self.after)

    def undo(self, sidecar: Path) -> None:
        apply_targets(sidecar, self.scene, self.before)


def edit_for_plan(sidecar: Path, scene: str, plan: MovePlan, fps: float) -> CueEdit:
    """Build the undoable edit for a drop (preview frames → seconds)."""
    data = cue_store.load(sidecar)
    have = data.scenes.get(scene, {})
    before = {
        n: (have[n].target_frame / data.frame_rate if n in have and not have[n].tombstone else None)
        for n in plan.targets
    }
    after = {n: f / fps for n, f in plan.targets.items()}
    verb = "Ripple" if plan.ripple and len(plan.targets) > 1 else "Move"
    return CueEdit(scene, before, after, f"{verb} cue {plan.name!r}")


def edit_reset(sidecar: Path, scene: str, name: str) -> CueEdit:
    data = cue_store.load(sidecar)
    have = data.scenes.get(scene, {})
    before = have[name].target_frame / data.frame_rate if name in have else None
    return CueEdit(scene, {name: before}, {name: None}, f"Reset cue {name!r} to its default")
